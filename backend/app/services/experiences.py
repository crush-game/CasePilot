"""从明确确认的结案记录生成待审经验。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.contracts import SCOPE_FIELDS
from app.api.schemas import ExperienceView
from app.domain.errors import AppError
from app.repositories.database import get_engine
from app.repositories.models import AuditEvent, Experience
from app.services.tickets import reserve_request
from app.services.workflow_common import latest_snapshot
from app.tools.redaction import redact


def enqueue_candidate(db, ticket, run, action_id):
    result = ticket.result_json
    request = latest_snapshot(db, run.id)["request"] if run else {}
    scope_fields = (*SCOPE_FIELDS, "platform", "app_version")
    solution = ticket.solution_json
    db.add(Experience(
        source_ticket_id=ticket.id, source_run_id=run.id if run else None,
        source_action_id=action_id, result_version=ticket.version,
        content_json={
            "data_source": result["data_source"], "confirmation": result["confirmation"],
            "result_note": redact(result["reason"]), "verified_steps": redact(result["verified_steps"] or ""),
            "problem": redact(ticket.feedback_text, limit=2000),
            "conditions": {key: redact(request[key]) for key in scope_fields if request.get(key)},
            "evidence_refs": solution.get("evidence_refs", []) if solution.get("draft_validation") == "passed" else [],
        },
    ))


def process_candidate(ticket_id=None):
    # 单次纯本地事务。进程中断由数据库回滚，多个 Worker 不会重复提取。
    with Session(get_engine()) as db:
        query = select(Experience).where(Experience.status == "queued")
        if ticket_id is not None:
            query = query.where(Experience.source_ticket_id == ticket_id)
        row = db.scalar(query.order_by(Experience.created_at, Experience.id).limit(1).with_for_update(skip_locked=True))
        if row is None:
            return False
        row.content_json = {**row.content_json, "limitations": [
            "仅记录单次明确确认的结果，适用性需要复核。",
            *([] if row.content_json["verified_steps"] else ["未记录经核验的有效措施。"]),
        ]}
        row.status = "candidate"
        db.commit()
        return True


def review(db, actor, experience_id, body):
    operation = "experiences.review"
    payload = body.model_dump(mode="json")
    record, replay = reserve_request(db, actor.id, f"{operation}:{experience_id}", str(body.action_id), payload)
    if replay:
        return record.response_ref
    row = db.scalar(select(Experience).where(Experience.id == experience_id,
                                            Experience.status != "queued").with_for_update())
    if row is None:
        raise AppError(404, "EXPERIENCE_NOT_FOUND", "经验候选不存在")
    if row.version != body.expected_version:
        raise AppError(409, "VERSION_CONFLICT", "候选已发生变化，请刷新后重试")
    if row.status == "archived" or (body.decision == "review" and row.status != "candidate"):
        raise AppError(409, "INVALID_STATE", "当前状态不允许此审阅操作")
    row.status = "reviewed" if body.decision == "review" else "archived"
    row.version += 1
    row.review_json = {"decision": body.decision, "reason": redact(body.reason), "actor_id": str(actor.id)}
    response = ExperienceView.model_validate(row).model_dump(mode="json")
    record.response_ref = response
    db.add(AuditEvent(
        action_id=body.action_id, actor_id=actor.id, ticket_id=row.source_ticket_id,
        expected_version=body.expected_version, operation=operation,
        patch={"experience_id": str(row.id), **row.review_json},
        result={"experience_id": str(row.id), "status": row.status, "version": row.version},
    ))
    db.commit()
    return response
