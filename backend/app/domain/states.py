from app.domain.enums import TicketStatus
from app.domain.errors import AppError


TRANSITIONS = {
    TicketStatus.QUEUED: {TicketStatus.RUNNING, TicketStatus.RESOLVED, TicketStatus.CLOSED_UNRESOLVED},
    TicketStatus.RUNNING: {TicketStatus.PENDING_CONFIRMATION, TicketStatus.WAITING_HUMAN},
    TicketStatus.WAITING_HUMAN: {TicketStatus.QUEUED, TicketStatus.RESOLVED, TicketStatus.CLOSED_UNRESOLVED},
    TicketStatus.PENDING_CONFIRMATION: {TicketStatus.WAITING_CUSTOMER, TicketStatus.QUEUED, TicketStatus.RESOLVED, TicketStatus.CLOSED_UNRESOLVED},
    TicketStatus.WAITING_CUSTOMER: {TicketStatus.QUEUED, TicketStatus.RESOLVED, TicketStatus.CLOSED_UNRESOLVED},
    TicketStatus.RESOLVED: set(),
    TicketStatus.CLOSED_UNRESOLVED: set(),
}
TERMINAL_STATUSES = {TicketStatus.RESOLVED, TicketStatus.CLOSED_UNRESOLVED}


def require_transition(current: TicketStatus, target: TicketStatus):
    if target not in TRANSITIONS[current]:
        raise AppError(409, "INVALID_STATE", "当前工单状态不允许该操作")
