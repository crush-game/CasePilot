from enum import StrEnum


class Role(StrEnum):
    BUSINESS = "business"
    KNOWLEDGE_ADMIN = "knowledge_admin"


class TicketStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_HUMAN = "WAITING_HUMAN"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    PENDING_CONFIRMATION = "PENDING_CONFIRMATION"
    RESOLVED = "RESOLVED"
    CLOSED_UNRESOLVED = "CLOSED_UNRESOLVED"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class HumanTaskStatus(StrEnum):
    UNCLAIMED = "unclaimed"
    CLAIMED = "claimed"
    RESUMING = "resuming"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
