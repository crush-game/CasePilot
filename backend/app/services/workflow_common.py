from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.enums import TicketStatus
from app.domain.errors import AppError
from app.domain.states import require_transition
from app.repositories.models import AuditEvent, CaseSnapshot, Run, Ticket, TicketEvent
from app.services.tickets import digest


def lock_ticket(db: Session, ticket_id: UUID, expected_version: int | None = None):
    ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id).with_for_update())
    if ticket is None:
        raise AppError(404, "TICKET_NOT_FOUND", "工单不存在")
    if expected_version is not None and ticket.version != expected_version:
        raise AppError(409, "VERSION_CONFLICT", "工单已发生变化，请刷新后重试")
    return ticket


def require_run_lock(db: Session, run_id: UUID):
    available = db.scalar(text("SELECT pg_try_advisory_xact_lock(hashtextextended(:run_id, 0))"), {"run_id": str(run_id)})
    if not available:
        raise AppError(409, "RUN_BUSY", "运行尚未停止，请先请求接管并等待")


def transition(ticket: Ticket, target: TicketStatus):
    require_transition(TicketStatus(ticket.status), target)
    ticket.status = target
    ticket.version += 1
    ticket.updated_at = func.now()


def save_snapshot(db: Session, ticket: Ticket, run: Run, state: dict):
    run.case_version = ticket.version
    value = {**state, "ticket_id": str(ticket.id), "run_id": str(run.id), "case_version": ticket.version,
             "ticket_metadata": {"priority": ticket.priority, "assignee_id": str(ticket.assignee_id) if ticket.assignee_id else None}}
    db.add(CaseSnapshot(run_id=run.id, case_version=ticket.version, state_json=value, checksum=digest(value)))


def latest_snapshot(db: Session, run_id: UUID) -> dict:
    snapshot = db.scalar(select(CaseSnapshot).where(CaseSnapshot.run_id == run_id).order_by(CaseSnapshot.case_version.desc()).limit(1))
    if snapshot is None:
        raise AppError(409, "RUN_SNAPSHOT_MISSING", "运行快照缺失，请核查数据一致性")
    return snapshot.state_json


def ordered_nodes(nodes):
    # 子图的多个完成步骤可同事务投影，时间戳相同或回拨时仍以检查点逻辑序号为准。
    def position(node):
        suffix = node.logical_step_id.rsplit(":", 1)[-1]
        return (0, int(suffix)) if suffix.isdecimal() else (1, node.created_at, str(node.id))
    return sorted(nodes, key=position)


def append_event(db: Session, ticket: Ticket, event_type: str, payload: dict, run_id=None):
    db.add(TicketEvent(ticket_id=ticket.id, run_id=run_id or ticket.active_run_id,
                       event_type=event_type, payload_json={**payload, "version": ticket.version}))


def audit_action(db: Session, ticket: Ticket, actor_id: UUID, body, operation: str, result: dict):
    db.add(AuditEvent(
        action_id=body.action_id, actor_id=actor_id, ticket_id=ticket.id,
        expected_version=body.expected_version, operation=operation,
        patch=body.model_dump(mode="json"), result=result,
    ))
