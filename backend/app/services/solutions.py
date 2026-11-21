from uuid import UUID

from sqlalchemy import select

from app.agents.contracts import SCOPE_FIELDS
from app.domain.errors import AppError
from app.faults.tools import evidence_view
from app.knowledge.index import get_citation
from app.knowledge.schemas import KnowledgeScope
from app.repositories.models import ToolExecution
from app.tools.redaction import redact


FACT_FIELDS = (*SCOPE_FIELDS, "platform", "app_version", "occurred_at")


def check_draft(db, ticket, run, state, draft):
    refs = draft.get("evidence_refs")
    if (not isinstance(refs, list) or not refs or any(not isinstance(ref, str) for ref in refs)
            or not all(isinstance(draft.get(key), str) and draft[key].strip()
                       for key in ("internal_plan", "reply_draft")) or draft.get("data_source") != ticket.data_source):
        raise AppError(409, "INVALID_SOLUTION", "方案缺少建议、回复草稿或证据")
    refs = list(dict.fromkeys(refs))
    if not set(refs) <= set(state.get("evidence_refs", [])):
        raise AppError(409, "UNTRUSTED_MODEL_EVIDENCE", "方案包含未在本次调查取得的引用")

    request = state["request"]
    pins = {}
    mock_refs = set()
    if run.graph_version == "mock-v1":
        executions = db.scalars(select(ToolExecution).where(ToolExecution.run_id == run.id,
                                                           ToolExecution.status == "succeeded"))
        for execution in executions:
            value = execution.result_refs
            if value.get("data_source") == "mock":
                mock_refs.update(value.get("evidence_refs", []))

    for ref in refs:
        kind, _, identifier = ref.partition(":")
        try:
            if kind == "mock" and ref in mock_refs:
                continue
            if kind == "kb":
                scope = KnowledgeScope(**{key: request.get(key) for key in SCOPE_FIELDS})
                citation = get_citation(db, UUID(identifier), scope, commit=False).model_dump(mode="json")
            elif kind == "logev":
                citation = evidence_view(db, ticket.id, UUID(identifier), run_id=run.id, request=request)
            else:
                raise ValueError()
        except (ValueError, AppError):
            raise AppError(409, "EVIDENCE_NOT_APPLICABLE", "引用无法回源，请重新调查") from None
        if not citation["usable"]:
            raise AppError(409, "EVIDENCE_NOT_APPLICABLE", "引用已失效或与当前工单不匹配，请重新调查")
        pins[ref] = {"content_hash": citation["content_hash"], "source_checksum": citation["source_checksum"]}
    if "citation_checksums" in draft and draft["citation_checksums"] != pins:
        raise AppError(409, "EVIDENCE_NOT_APPLICABLE", "引用内容已变化，请重新调查")

    reports = [item["result"] for item in state.get("knowledge_history", [])]
    if state.get("fault_report"):
        reports.append(state["fault_report"])
    observations = [
        {"point": redact(finding["point"]), "applicability": redact(finding["applicability"]),
         "evidence_refs": finding["evidence_refs"]}
        for report in reports for finding in report["findings"]
        if finding["evidence_refs"] and set(finding["evidence_refs"]) <= set(refs)
    ]
    return {**draft, "evidence_refs": refs, "citation_checksums": pins,
            "confirmed_facts": {key: request[key] for key in FACT_FIELDS if request.get(key)},
            "observations": observations, "draft_validation": "passed"}
