import base64
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, select, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.api.schemas import TicketCreate, TicketCreated, TicketPatch, TicketView
from app.domain.enums import Role, TicketStatus
from app.domain.errors import AppError
from app.repositories.models import (
    AppUser, AuditEvent, CaseSnapshot, ExecutionTask, IdempotencyRecord,
    Run, Ticket, TicketEvent, TicketFact,
)


def digest(value: dict) -> str:
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def reserve_request(db: Session, actor_id: UUID, operation: str, key: str, payload: dict):
    request_hash = digest(payload)
    record_id = db.scalar(insert(IdempotencyRecord).values(
        id=uuid4(), actor_id=actor_id, operation=operation, key=key,
        request_hash=request_hash, response_ref={},
    ).on_conflict_do_nothing(constraint="uq_idempotency_scope").returning(IdempotencyRecord.id))
    if record_id:
        return db.get(IdempotencyRecord, record_id), False
    # 唯一约束使并发请求等待首个事务；后续 SELECT 读取其已提交结果。
    record = db.scalar(select(IdempotencyRecord).where(
        IdempotencyRecord.actor_id == actor_id, IdempotencyRecord.operation == operation,
        IdempotencyRecord.key == key,
    ))
    if record.request_hash != request_hash:
        raise AppError(409, "IDEMPOTENCY_CONFLICT", "同一操作标识已用于不同请求")
    return record, True


def get_ticket(db: Session, ticket_id: UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if not ticket:
        raise AppError(404, "TICKET_NOT_FOUND", "工单不存在")
    return ticket


def create_ticket(db: Session, actor: AppUser, key: str, body: TicketCreate) -> dict:
    payload = body.model_dump(mode="json")
    record, replay = reserve_request(db, actor.id, "tickets.create", key, payload)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket_id, run_id, task_id = uuid4(), uuid4(), uuid4()
    action_id = record.id
    ticket = Ticket(
        id=ticket_id, ticket_no=f"CP-{datetime.now(timezone.utc):%Y%m%d}-{ticket_id.hex}",
        customer_email=body.customer_email, feedback_text=body.feedback_text,
        device_ref=body.device_ref, occurred_at=body.occurred_at,
        occurred_at_original=body.occurred_at.isoformat() if body.occurred_at else None,
        occurred_at_precision=body.occurred_at_precision, priority=body.priority,
        created_by=actor.id, active_run_id=None,
    )
    db.add(ticket)
    db.flush()
    from app.agents.contracts import configuration_snapshot, SCOPE_FIELDS
    execution = configuration_snapshot()
    run = Run(
        id=run_id, ticket_id=ticket_id, thread_id=str(run_id),
        graph_version=execution.get("graph_version", "mock-v1"), case_version=1,
    )
    db.add(run)
    db.flush()
    ticket.active_run_id = run_id
    db.add(ExecutionTask(id=task_id, run_id=run_id, kind="start", action_id=action_id))
    state = {
        "ticket_id": str(ticket_id), "run_id": str(run_id), "case_version": 1,
        "request": payload, "data_source": "mock", "evidence_refs": [], **execution,
        "ticket_metadata": {"priority": body.priority, "assignee_id": None},
    }
    db.add(CaseSnapshot(run_id=run_id, case_version=1, state_json=state, checksum=digest(state)))
    for field in ("customer_email", "feedback_text", "device_ref", "occurred_at", *SCOPE_FIELDS):
        if payload[field] is not None:
            db.add(TicketFact(
                ticket_id=ticket_id, field=field, value_json={"value": payload[field]},
                source_type="user", source_ref=str(action_id), fact_version=1, actor_id=actor.id,
            ))
    db.add(TicketEvent(
        ticket_id=ticket_id, run_id=run_id, event_type="ticket.created",
        payload_json={"status": TicketStatus.QUEUED, "version": 1, "actor_id": str(actor.id)},
    ))
    result = TicketCreated(
        ticket_id=ticket_id, ticket_no=ticket.ticket_no, run_id=run_id,
        task_id=task_id, version=1, status=TicketStatus.QUEUED,
    ).model_dump(mode="json")
    record.response_ref = result
    db.add(AuditEvent(
        action_id=action_id, actor_id=actor.id, ticket_id=ticket_id,
        operation="tickets.create", patch={"source": "manual"}, result=result,
    ))
    # 所有对象和幂等响应一起提交，提交失败时不能向调用者返回 202。
    db.commit()
    return result


def patch_ticket(db: Session, actor: AppUser, ticket_id: UUID, body: TicketPatch) -> dict:
    payload = body.model_dump(mode="json", exclude_unset=True)
    record, replay = reserve_request(db, actor.id, f"tickets.update:{ticket_id}", str(body.action_id), payload)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket = get_ticket(db, ticket_id)
    if ticket.status != TicketStatus.QUEUED:
        raise AppError(409, "INVALID_STATE", "当前仅允许修改排队工单的优先级与负责人")
    patch = body.model_dump(exclude_unset=True, exclude={"action_id", "expected_version"})
    if patch.get("assignee_id") is not None:
        assignee = db.get(AppUser, patch["assignee_id"])
        if not assignee or not assignee.active or assignee.role != Role.BUSINESS:
            raise AppError(422, "INVALID_ASSIGNEE", "负责人必须是启用的业务账号")
    changed = db.scalar(update(Ticket).where(
        Ticket.id == ticket_id, Ticket.version == body.expected_version,
        Ticket.status == TicketStatus.QUEUED,
    ).values(**patch, version=Ticket.version + 1, updated_at=func.now()).returning(Ticket)
        .execution_options(populate_existing=True))
    if changed is None:
        raise AppError(409, "VERSION_CONFLICT", "工单已发生变化，请刷新后重试")
    run = db.get(Run, changed.active_run_id)
    if run is None or run.status != "queued":
        raise AppError(409, "INVALID_STATE", "运行状态已变化，请刷新后重试")
    snapshot = db.scalar(select(CaseSnapshot).where(
        CaseSnapshot.run_id == run.id, CaseSnapshot.case_version == run.case_version,
    ))
    if snapshot is None:
        raise AppError(409, "RUN_SNAPSHOT_MISSING", "运行快照缺失，请先核查数据一致性")
    state = {**snapshot.state_json, "case_version": changed.version, "ticket_metadata": {
        "priority": changed.priority, "assignee_id": str(changed.assignee_id) if changed.assignee_id else None,
    }}
    run.case_version = changed.version
    db.add(CaseSnapshot(run_id=run.id, case_version=changed.version, state_json=state, checksum=digest(state)))
    result = TicketView.model_validate(changed).model_dump(mode="json")
    public_patch = payload.copy()
    db.add(TicketEvent(
        ticket_id=ticket_id, run_id=changed.active_run_id, event_type="ticket.updated",
        payload_json={"patch": public_patch, "version": changed.version, "actor_id": str(actor.id)},
    ))
    db.add(AuditEvent(
        action_id=body.action_id, actor_id=actor.id, ticket_id=ticket_id,
        expected_version=body.expected_version, operation="tickets.update",
        patch=public_patch, result={"version": changed.version},
    ))
    record.response_ref = result
    db.commit()
    return result


def list_tickets(db: Session, limit: int, cursor: str | None, status, priority, assignee_id):
    query = select(Ticket)
    filters = {"status": status, "priority": priority, "assignee_id": str(assignee_id) if assignee_id else None}
    for name, value in (("status", status), ("priority", priority), ("assignee_id", assignee_id)):
        if value is not None:
            query = query.where(getattr(Ticket, name) == value)
    if cursor:
        try:
            data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            created_at = datetime.fromisoformat(data["created_at"])
            ticket_id = UUID(data["id"])
            if created_at.tzinfo is None or data["filters"] != filters:
                raise ValueError
        except (ValueError, KeyError, TypeError, UnicodeError):
            raise AppError(422, "INVALID_CURSOR", "分页游标无效或筛选条件已变化") from None
        query = query.where(tuple_(Ticket.created_at, Ticket.id) < tuple_(created_at, ticket_id))
    rows = list(db.scalars(query.order_by(Ticket.created_at.desc(), Ticket.id.desc()).limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(json.dumps({
            "created_at": last.created_at.isoformat(), "id": str(last.id), "filters": filters,
        }).encode()).decode()
    return {"items": rows[:limit], "next_cursor": next_cursor}
