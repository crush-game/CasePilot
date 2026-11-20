"""受控只读工具：身份来自当前工单，句柄与脱敏证据在PostgreSQL持久保存。"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.domain.errors import AppError
from app.faults.contracts import FaultObservation, FaultToolArgs
from app.faults.logs import MAX_INPUT, archive_bytes, parse_log
from app.faults.source import CONTEXT_FIELDS, context_hash, feedbacks, load_source, require_feedback, timestamp
from app.providers.ledger import ProviderFailure
from app.repositories.models import LogArtifact, LogEvidence, Run, Ticket
from app.services.workflow_common import latest_snapshot
from app.tools.redaction import redact


def evidence_view(db, ticket_id, evidence_id, *, run_id=None, request=None):
    row = db.scalar(select(LogEvidence).where(LogEvidence.id == evidence_id, LogEvidence.ticket_id == ticket_id))
    if row is None:
        raise AppError(404, "EVIDENCE_NOT_FOUND", "此工单不存在该证据")
    ticket = db.get(Ticket, ticket_id)
    artifact = db.get(LogArtifact, row.artifact_id)
    target = run_id or ticket.active_run_id
    facts = request if request is not None else latest_snapshot(db, row.run_id)["request"]
    usable = target == row.run_id and artifact.context_hash == context_hash(ticket_id, facts)
    if hashlib.sha256(artifact.original_bytes).hexdigest() != artifact.checksum or hashlib.sha256(row.text.encode()).hexdigest() != row.content_hash:
        usable = False
    return {"ref": "logev:" + row.id.hex, "title": f"{row.domain} · {row.member_name}:{row.line_number}", "text": row.text,
        "data_source": "mock", "source_type": artifact.source_kind, "domain": row.domain, "occurred_at": row.occurred_at.isoformat(),
        "start_line": row.line_number, "end_line": row.line_number, "usable": usable, "content_hash": row.content_hash,
        "source_checksum": artifact.checksum, "metadata": {"artifact_ref": "artifact:" + artifact.id.hex,
            "feedback_ref": artifact.feedback_ref, "member_name": row.member_name, "line_number": row.line_number,
            "source_kind": artifact.source_kind, "domain": row.domain, "occurred_at": row.occurred_at.isoformat()},
        "product_scope": [facts.get("product_ref") or "*"], "firmware_versions": [facts.get("firmware_version") or "*"]}


class FaultTools:
    ALLOWED = {"get_feedbacks", "download_log", "extract_log_window", "get_wifi_telemetry", "diagnose_wifi"}

    def __init__(self, ctx, state):
        self.ctx, self.state = ctx, state
        self.request = state["request"]
        self.config = state["agent_config"]["enterprise"]

    def email(self):
        with Session(self.ctx.engine) as db:
            ticket, _, _ = self.ctx.fenced(db)
            return ticket.customer_email

    def call(self, name, args):
        source = {"data_source": "mock", "adapter": "mock-feedback-log-v1", "query": {},
                  "fixture_checksum": self.config["checksum"]}
        try:
            args = FaultToolArgs.model_validate(args)
            source["query"] = {"customer_ref": str(self.ctx.ticket_id),
                **{key: self.request.get(key) for key in CONTEXT_FIELDS}, **args.model_dump(mode="json")}
            if name not in self.ALLOWED:
                raise ProviderFailure("TOOL_NOT_ALLOWED")
            data = load_source(self.config)
            failure = data.get("tool_errors", {}).get(name)
            if failure:
                raise ProviderFailure(failure if failure in {"AUTH_FAILED", "TIMEOUT", "RATE_LIMITED", "DOWNLOAD_FAILED", "PARSE_FAILED"} else "TOOL_FAILED")
            payload, refs, status, code = getattr(self, name)(data, args)
            return FaultObservation(status=status, data=payload, data_refs=refs, error_code=code,
                source=source, fetched_at=datetime.now(timezone.utc).isoformat()).model_dump(mode="json")
        except ProviderFailure as exc:
            return FaultObservation(status="error", error_code=exc.code, retryable=False, source=source,
                fetched_at=datetime.now(timezone.utc).isoformat()).model_dump(mode="json")
        except ValidationError:
            return FaultObservation(status="error", error_code="INVALID_ARGUMENTS", source=source,
                fetched_at=datetime.now(timezone.utc).isoformat()).model_dump(mode="json")
        except (ValueError, TypeError, KeyError):
            return FaultObservation(status="error", error_code="PARSE_FAILED", source=source,
                fetched_at=datetime.now(timezone.utc).isoformat()).model_dump(mode="json")

    def get_feedbacks(self, data, args):
        missing = [key for key in ("device_ref", "occurred_at") if not self.request.get(key)]
        if missing:
            return {"records": [], "missing_fields": missing}, [], "needs_human", "MISSING_FACTS"
        rows, code = feedbacks(data, self.email(), self.request)
        values = [{key: row.get(key) for key in ("record_id", "device_ref", "platform", "product_ref", "firmware_version", "app_version", "occurred_at")}
                  | {"summary": redact(row.get("summary", "")), "attachment_available": bool(row.get("archive_ref"))} for row in rows]
        return {"records": values}, [row["record_id"] for row in rows], "success" if rows else "no_data", code

    def owned_feedback(self, args):
        if not args.feedback_ref:
            raise ProviderFailure("FEEDBACK_REQUIRED")
        return require_feedback(self.config, self.email(), self.request, args.feedback_ref)

    def save_artifact(self, feedback, raw, kind, media_type):
        if not raw or len(raw) > MAX_INPUT:
            raise ProviderFailure("LOG_LIMIT_EXCEEDED")
        identifier = uuid5(self.ctx.run_id, f"{kind}:{feedback['record_id']}")
        checksum = hashlib.sha256(raw).hexdigest()
        with Session(self.ctx.engine) as db:
            self.ctx.fenced(db)
            old = db.get(LogArtifact, identifier)
            if old and (old.checksum != checksum or old.context_hash != context_hash(self.ctx.ticket_id, self.request)):
                raise ProviderFailure("ARTIFACT_CONTEXT_CHANGED")
            if not old:
                db.add(LogArtifact(id=identifier, run_id=self.ctx.run_id, ticket_id=self.ctx.ticket_id,
                    feedback_ref=feedback["record_id"], source_kind=kind, checksum=checksum, media_type=media_type,
                    context_hash=context_hash(self.ctx.ticket_id, self.request), original_bytes=raw,
                    metadata_json={key: feedback.get(key) for key in ("device_ref", "product_ref", "firmware_version", "platform", "app_version", "occurred_at")}))
            db.commit()
        return {"artifact_ref": "artifact:" + identifier.hex, "checksum": checksum, "size_bytes": len(raw), "source_kind": kind}

    def download_log(self, data, args):
        data, row = self.owned_feedback(args)
        if not row.get("archive_ref"):
            return {}, [], "no_data", "NO_ATTACHMENT"
        files = data.get("archives", {}).get(row["archive_ref"])
        if files is None:
            raise ProviderFailure("DOWNLOAD_FAILED")
        result = self.save_artifact(row, archive_bytes(files), "detailed_log", "application/zip")
        return result, [result["artifact_ref"]], "success", None

    def get_wifi_telemetry(self, data, args):
        data, row = self.owned_feedback(args)
        if row.get("archive_ref"):
            raise ProviderFailure("DETAILED_LOG_REQUIRED")
        records = [value for value in data.get("telemetry", []) if value.get("feedback_ref") == row["record_id"]
                   and all(value.get(key) == row.get(key) for key in ("device_ref", "platform", "firmware_version"))]
        if not records:
            return {}, [], "no_data", "NO_TELEMETRY"
        raw = "\n".join(json.dumps({"occurred_at": value["occurred_at"], "domain": "wifi", "text": value["text"]}, ensure_ascii=False) for value in records).encode()
        result = self.save_artifact(row, raw, "telemetry", "text/plain")
        return result, [result["artifact_ref"]], "success", None

    def extract_log_window(self, data, args):
        try:
            identifier = UUID((args.artifact_ref or "").removeprefix("artifact:"))
        except ValueError:
            raise ProviderFailure("FORBIDDEN") from None
        with Session(self.ctx.engine, expire_on_commit=False) as db:
            artifact = db.scalar(select(LogArtifact).where(LogArtifact.id == identifier, LogArtifact.run_id == self.ctx.run_id,
                                                          LogArtifact.ticket_id == self.ctx.ticket_id))
            if artifact is None or artifact.context_hash != context_hash(self.ctx.ticket_id, self.request):
                raise ProviderFailure("FORBIDDEN")
            if hashlib.sha256(artifact.original_bytes).hexdigest() != artifact.checksum:
                raise ProviderFailure("ARTIFACT_CORRUPTED")
            parsed = parse_log(artifact.original_bytes, artifact.media_type)
            point = timestamp(self.request["occurred_at"])
            radius = timedelta(minutes=15 if args.window_kind == "expanded" else 5)
            start, end = point - radius, point + radius
            matching = [value for value in parsed if start <= value["occurred_at"] <= end]
            selected = matching[:40]
            self.ctx.fenced(db)
            refs = []
            for value in selected:
                eid = uuid5(identifier, f"{value['member_name']}:{value['line_number']}")
                db.execute(insert(LogEvidence).values(id=eid, artifact_id=identifier, run_id=self.ctx.run_id,
                    ticket_id=self.ctx.ticket_id, **value).on_conflict_do_nothing(constraint="uq_log_evidence_line"))
                refs.append("logev:" + eid.hex)
            db.commit()
            views = [evidence_view(db, self.ctx.ticket_id, UUID(ref.removeprefix("logev:")), run_id=self.ctx.run_id, request=self.request) for ref in refs]
        result = {"evidence": views, "source_kind": artifact.source_kind, "viewed_range": {"start": start.isoformat(), "end": end.isoformat()},
                  "matching_records": len(matching), "coverage_complete": len(matching) <= 40}
        return result, refs, "success" if refs else "no_data", None if refs else "NO_MATCHING_RECORD"

    def diagnose_wifi(self, data, args):
        refs = self.state.get("fault_window_refs", [])
        with Session(self.ctx.engine) as db:
            views = [evidence_view(db, self.ctx.ticket_id, UUID(ref.removeprefix("logev:")), run_id=self.ctx.run_id, request=self.request) for ref in refs]
        values = [row for row in views if row["usable"] and row["domain"] == "wifi"]
        if not values:
            return {}, [], "no_data", "NO_MATCHING_RECORD"
        return {"analysis_mode": "rule", "domain": "wifi", "findings": [
            {"point": ("可见断连事件：" if "disconnect" in row["text"].casefold() else "可见WiFi记录：") + row["occurred_at"],
             "applicability": "仅为当前设备/版本和查看时间窗的观察，不证明根因。", "evidence_refs": [row["ref"]]}
            for row in values[:4]], "candidate_causes": [], "limitations": ["规则仅报告可见记录，时间先后不证明因果。"]}, [row["ref"] for row in values], "success", None
