from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Identity, Index, Integer, MetaData, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.enums import HumanTaskStatus, Priority, Role, RunStatus, TaskStatus, TicketStatus


SCHEMA = "business"
SCHEMA_VERSION = "0002_runtime"


def choices(column, enum):
    return f"{column} IN ({', '.join(repr(item.value) for item in enum)})"


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class AppUser(Base):
    __tablename__ = "app_users"
    __table_args__ = (CheckConstraint(choices("role", Role), name="role"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    login: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Ticket(Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(choices("status", TicketStatus), name="status"),
        CheckConstraint(choices("priority", Priority), name="priority"),
        CheckConstraint("version >= 1", name="version"),
        UniqueConstraint("id", "active_run_id", name="uq_tickets_id_active_run"),
        # 延迟检查，允许同一事务插入 ticket 与 run；同时防止指向其他工单的 run。
        ForeignKeyConstraint(
            ["active_run_id", "id"], ["business.runs.id", "business.runs.ticket_id"],
            name="fk_tickets_active_run", use_alter=True, deferrable=True, initially="DEFERRED",
        ),
        Index("ix_tickets_status_assignee_created", "status", "assignee_id", "created_at"),
        Index("ix_tickets_created_id", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_no: Mapped[str] = mapped_column(String(48), unique=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    data_source: Mapped[str] = mapped_column(String(16), default="mock")
    customer_email: Mapped[str] = mapped_column(String(254))
    feedback_text: Mapped[str] = mapped_column(Text)
    device_ref: Mapped[str | None] = mapped_column(String(128))
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    occurred_at_original: Mapped[str | None] = mapped_column(String(64))
    occurred_at_precision: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(32), default=TicketStatus.QUEUED)
    priority: Mapped[str] = mapped_column(String(16), default=Priority.NORMAL)
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.app_users.id"))
    created_by: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    active_run_id: Mapped[UUID | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    solution_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    result_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class Run(Base):
    __tablename__ = "runs"
    __table_args__ = (
        CheckConstraint(choices("status", RunStatus), name="status"),
        CheckConstraint("case_version >= 1", name="case_version"),
        UniqueConstraint("id", "ticket_id", name="uq_runs_id_ticket"),
        Index("uq_runs_active_ticket", "ticket_id", unique=True,
              postgresql_where=text("status IN ('queued','running','paused')")),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("business.tickets.id"))
    thread_id: Mapped[str] = mapped_column(String(64), unique=True)
    graph_version: Mapped[str] = mapped_column(String(64))
    case_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default=RunStatus.QUEUED)
    checkpoint_ref: Mapped[dict | None] = mapped_column(JSONB)
    budget_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    stop_reason: Mapped[str | None] = mapped_column(String(128))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExecutionTask(Base):
    __tablename__ = "execution_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "kind", "action_id", name="uq_tasks_logical_action"),
        CheckConstraint(choices("status", TaskStatus), name="status"),
        CheckConstraint("attempt >= 0", name="attempt"),
        Index("ix_tasks_status_available", "status", "available_at"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("business.runs.id"))
    kind: Mapped[str] = mapped_column(String(32))
    action_id: Mapped[UUID] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.QUEUED)
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column()
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketFact(Base):
    __tablename__ = "ticket_facts"
    __table_args__ = (UniqueConstraint("ticket_id", "field", "fact_version", name="uq_facts_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("business.tickets.id"))
    field: Mapped[str] = mapped_column(String(64))
    value_json: Mapped[dict] = mapped_column(JSONB)
    source_type: Mapped[str] = mapped_column(String(32))
    source_ref: Mapped[str] = mapped_column(String(128))
    fact_version: Mapped[int] = mapped_column(Integer)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseSnapshot(Base):
    __tablename__ = "case_snapshots"
    __table_args__ = (UniqueConstraint("run_id", "case_version", name="uq_snapshots_version"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("business.runs.id"))
    case_version: Mapped[int] = mapped_column(Integer)
    state_json: Mapped[dict] = mapped_column(JSONB)
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TicketEvent(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (Index("ix_events_ticket_id", "ticket_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("business.tickets.id"))
    run_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.runs.id"))
    event_type: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("actor_id", "operation", "key", name="uq_idempotency_scope"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    operation: Mapped[str] = mapped_column(String(128))
    key: Mapped[str] = mapped_column(String(128))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_ref: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    action_id: Mapped[UUID] = mapped_column(unique=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("business.tickets.id"), index=True)
    expected_version: Mapped[int | None] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(64))
    patch: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanTask(Base):
    __tablename__ = "human_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "pause_key", name="uq_human_tasks_pause"),
        CheckConstraint(choices("status", HumanTaskStatus), name="status"),
        Index("uq_human_tasks_open_ticket", "ticket_id", unique=True,
              postgresql_where=text("status IN ('unclaimed','claimed','resuming')")),
        Index("ix_human_tasks_status_created", "status", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    ticket_id: Mapped[UUID] = mapped_column(ForeignKey("business.tickets.id"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("business.runs.id"))
    pause_key: Mapped[str] = mapped_column(String(128))
    reason_code: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default=HumanTaskStatus.UNCLAIMED)
    assignee_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.app_users.id"))
    checkpoint_ref: Mapped[dict] = mapped_column(JSONB)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanAction(Base):
    __tablename__ = "human_actions"

    action_id: Mapped[UUID] = mapped_column(primary_key=True)
    human_task_id: Mapped[UUID] = mapped_column(ForeignKey("business.human_tasks.id"))
    run_id: Mapped[UUID] = mapped_column(ForeignKey("business.runs.id"), index=True)
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    expected_version: Mapped[int] = mapped_column(Integer)
    request_json: Mapped[dict] = mapped_column(JSONB)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_checkpoint: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class NodeRun(Base):
    __tablename__ = "node_runs"
    __table_args__ = (UniqueConstraint("run_id", "logical_step_id", "attempt", name="uq_node_runs_step"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("business.runs.id"), index=True)
    node_name: Mapped[str] = mapped_column(String(64))
    logical_step_id: Mapped[str] = mapped_column(String(160))
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    input_refs: Mapped[dict] = mapped_column(JSONB, default=dict)
    output_refs: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_version: Mapped[str | None] = mapped_column(String(64))
    usage_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (UniqueConstraint("run_id", "logical_action_id", name="uq_tool_executions_action"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("business.runs.id"))
    logical_action_id: Mapped[UUID] = mapped_column()
    tool_name: Mapped[str] = mapped_column(String(64))
    args_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    result_refs: Mapped[dict] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
