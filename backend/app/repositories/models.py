from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint,
    Identity, Index, Integer, LargeBinary, MetaData, Numeric, String, Text, UniqueConstraint, func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.domain.enums import HumanTaskStatus, Priority, Role, RunStatus, TaskStatus, TicketStatus


SCHEMA = "business"
SCHEMA_VERSION = "0008_delivery"


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


class KBDocument(Base):
    __tablename__ = "kb_documents"
    __table_args__ = (
        UniqueConstraint("doc_key", "version", name="uq_kb_documents_key_version"),
        CheckConstraint("version >= 1 AND revision >= 1", name="versions"),
        CheckConstraint("status IN ('pending','active','failed','archived','superseded')", name="status"),
        CheckConstraint("effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from", name="effective_range"),
        CheckConstraint("data_source = 'mock' AND retrieval_mode IN ('bm25','hybrid')", name="mode"),
        Index("uq_kb_documents_active_key", "doc_key", unique=True, postgresql_where=text("status = 'active'")),
        Index("ix_kb_documents_status_created", "status", "created_at", "id"),
        Index("ix_kb_documents_product_scope", "product_scope", postgresql_using="gin"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    doc_key: Mapped[str] = mapped_column(String(120))
    version: Mapped[int] = mapped_column(Integer)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200))
    filename: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(32))
    data_source: Mapped[str] = mapped_column(String(16), default="mock")
    retrieval_mode: Mapped[str] = mapped_column(String(16), default="bm25")
    product_scope: Mapped[list] = mapped_column(JSONB)
    firmware_versions: Mapped[list] = mapped_column(JSONB)
    regions: Mapped[list] = mapped_column(JSONB)
    channels: Mapped[list] = mapped_column(JSONB)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    checksum: Mapped[str] = mapped_column(String(64))
    original_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    index_version: Mapped[int | None] = mapped_column(BigInteger)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    audit_json: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBChunk(Base):
    __tablename__ = "kb_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_kb_chunks_document_ordinal"),
        CheckConstraint("ordinal >= 0 AND start_line >= 1 AND end_line >= start_line", name="positions"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("business.kb_documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    heading_path: Mapped[list] = mapped_column(JSONB)
    text: Mapped[str] = mapped_column(Text)
    start_line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64))
    metadata_json: Mapped[dict] = mapped_column(JSONB)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_ingestion_jobs_document"),
        CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name="status"),
        CheckConstraint("attempt >= 0 AND revision >= 1", name="versions"),
        Index("ix_ingestion_jobs_status_created", "status", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("business.kb_documents.id"))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    stage: Mapped[str] = mapped_column(String(32), default="queued")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    error_code: Mapped[str | None] = mapped_column(String(64))
    retryable: Mapped[bool] = mapped_column(Boolean, default=False)
    lease_token: Mapped[UUID | None] = mapped_column()
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    index_version: Mapped[int | None] = mapped_column(BigInteger)
    history_json: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBIndexState(Base):
    __tablename__ = "kb_index_state"
    __table_args__ = (CheckConstraint("id = 1 AND version >= 0", name="singleton"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    snapshot_checksum: Mapped[str] = mapped_column(String(64), default="")
    active_profile_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.embedding_profiles.id"))


class ProviderBudget(Base):
    __tablename__ = "provider_budgets"
    __table_args__ = (CheckConstraint("max_calls > 0 AND max_tokens > 0 AND max_cost > 0 AND calls_used >= 0 AND tokens_used >= 0 AND exposure_cost >= 0", name="limits"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    scope: Mapped[str] = mapped_column(String(120))
    max_calls: Mapped[int] = mapped_column(Integer)
    max_tokens: Mapped[int] = mapped_column(BigInteger)
    max_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    currency: Mapped[str] = mapped_column(String(8))
    calls_used: Mapped[int] = mapped_column(Integer, default=0)
    tokens_used: Mapped[int] = mapped_column(BigInteger, default=0)
    exposure_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8), default=Decimal(0))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    budget_id: Mapped[UUID] = mapped_column(ForeignKey("business.provider_budgets.id"), index=True)
    operation: Mapped[str] = mapped_column(String(32))
    inference_mode: Mapped[str] = mapped_column(String(16))
    profile_json: Mapped[dict] = mapped_column(JSONB)
    request_hash: Mapped[str] = mapped_column(String(64))
    response_hash: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="reserved")
    error_code: Mapped[str | None] = mapped_column(String(64))
    reserved_tokens: Mapped[int] = mapped_column(BigInteger)
    reserved_cost: Mapped[Decimal] = mapped_column(Numeric(18, 8))
    usage_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    provider_request_id: Mapped[str | None] = mapped_column(String(200))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    __table_args__ = (UniqueConstraint("id", "dimensions", name="uq_embedding_profiles_id_dimensions"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    fingerprint: Mapped[str] = mapped_column(String(64), unique=True)
    dimensions: Mapped[int] = mapped_column(Integer)
    inference_mode: Mapped[str] = mapped_column(String(16))
    config_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KBEmbedding(Base):
    __tablename__ = "kb_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", "profile_id", name="uq_kb_embeddings_chunk_profile"),
        ForeignKeyConstraint(["profile_id", "dimensions"], ["business.embedding_profiles.id", "business.embedding_profiles.dimensions"],
                             name="fk_kb_embeddings_profile_dimensions"),
        CheckConstraint("vector_dims(embedding) = dimensions", name="dimensions"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    chunk_id: Mapped[UUID] = mapped_column(ForeignKey("business.kb_chunks.id"))
    profile_id: Mapped[UUID] = mapped_column()
    dimensions: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float]] = mapped_column(Vector())
    content_hash: Mapped[str] = mapped_column(String(64))
    provider_call_id: Mapped[UUID] = mapped_column(ForeignKey("business.provider_calls.id"))


class KBIndexBuild(Base):
    __tablename__ = "kb_index_builds"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    profile_id: Mapped[UUID] = mapped_column(ForeignKey("business.embedding_profiles.id"))
    budget_id: Mapped[UUID] = mapped_column(ForeignKey("business.provider_budgets.id"))
    base_version: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32), default="running")
    error_code: Mapped[str | None] = mapped_column(String(64))
    index_version: Mapped[int | None] = mapped_column(BigInteger)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LogArtifact(Base):
    __tablename__ = "log_artifacts"
    __table_args__ = (
        ForeignKeyConstraint(["run_id", "ticket_id"], ["business.runs.id", "business.runs.ticket_id"], name="fk_log_artifacts_run_ticket"),
        UniqueConstraint("id", "run_id", "ticket_id", name="uq_log_artifacts_owner"),
        UniqueConstraint("run_id", "feedback_ref", "source_kind", name="uq_log_artifacts_source"),
        CheckConstraint("source_kind IN ('detailed_log','telemetry') AND data_source = 'mock'", name="mode"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column()
    ticket_id: Mapped[UUID] = mapped_column()
    feedback_ref: Mapped[str] = mapped_column(String(120))
    source_kind: Mapped[str] = mapped_column(String(24))
    data_source: Mapped[str] = mapped_column(String(16), default="mock")
    checksum: Mapped[str] = mapped_column(String(64))
    context_hash: Mapped[str] = mapped_column(String(64))
    media_type: Mapped[str] = mapped_column(String(60))
    original_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    metadata_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LogEvidence(Base):
    __tablename__ = "log_evidence"
    __table_args__ = (
        ForeignKeyConstraint(["artifact_id", "run_id", "ticket_id"],
            ["business.log_artifacts.id", "business.log_artifacts.run_id", "business.log_artifacts.ticket_id"], name="fk_log_evidence_artifact_owner"),
        UniqueConstraint("artifact_id", "member_name", "line_number", name="uq_log_evidence_line"),
        CheckConstraint("line_number > 0", name="line"),
        Index("ix_log_evidence_run_time", "run_id", "occurred_at"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    artifact_id: Mapped[UUID] = mapped_column()
    run_id: Mapped[UUID] = mapped_column()
    ticket_id: Mapped[UUID] = mapped_column()
    member_name: Mapped[str] = mapped_column(String(200))
    line_number: Mapped[int] = mapped_column(Integer)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    domain: Mapped[str] = mapped_column(String(30))
    text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))


class Experience(Base):
    __tablename__ = "experiences"
    __table_args__ = (
        UniqueConstraint("source_ticket_id", "result_version", name="uq_experiences_result"),
        ForeignKeyConstraint(["source_run_id", "source_ticket_id"], ["business.runs.id", "business.runs.ticket_id"],
                             name="fk_experiences_run_ticket"),
        CheckConstraint("status IN ('queued','candidate','reviewed','archived')", name="status"),
        CheckConstraint("version >= 1 AND result_version >= 1", name="versions"),
        Index("ix_experiences_status_created", "status", "created_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    source_ticket_id: Mapped[UUID] = mapped_column(ForeignKey("business.tickets.id"))
    source_run_id: Mapped[UUID | None] = mapped_column()
    source_action_id: Mapped[UUID] = mapped_column(ForeignKey("business.audit_events.action_id", deferrable=True, initially="DEFERRED"), unique=True)
    result_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    content_json: Mapped[dict] = mapped_column(JSONB)
    review_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SupportConversation(Base):
    __tablename__ = "support_conversations"
    __table_args__ = (Index("ix_support_conversations_owner_created", "owner_id", "created_at", "id"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    ticket_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.tickets.id"), unique=True)
    context_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SupportTurn(Base):
    __tablename__ = "support_turns"
    __table_args__ = (Index("ix_support_turns_conversation_id", "conversation_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("business.support_conversations.id"))
    request_text: Mapped[str] = mapped_column(Text)
    reply_json: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ChannelThread(Base):
    __tablename__ = "channel_threads"
    __table_args__ = (UniqueConstraint("sender_id", "external_ref", "issue_ref", name="uq_channel_threads_issue"),)

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    sender_id: Mapped[UUID] = mapped_column(ForeignKey("business.app_users.id"))
    external_ref: Mapped[str] = mapped_column(String(120))
    issue_ref: Mapped[str] = mapped_column(String(120))
    conversation_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.support_conversations.id"), unique=True)
    reply_target: Mapped[str] = mapped_column(String(120))
    latest_sequence: Mapped[int] = mapped_column(Integer)


class ChannelEvent(Base):
    __tablename__ = "channel_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    thread_id: Mapped[UUID | None] = mapped_column(ForeignKey("business.channel_threads.id"))
    request_hash: Mapped[str] = mapped_column(String(64))
    event_json: Mapped[dict] = mapped_column(JSONB)
    response_json: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SupportDelivery(Base):
    __tablename__ = "support_deliveries"
    __table_args__ = (
        CheckConstraint("status IN ('queued','delivered','failed')", name="status"),
        CheckConstraint("channel IN ('app','mock')", name="channel"),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts"),
        Index("ix_support_deliveries_eligible", "status", "available_at", "id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    conversation_id: Mapped[UUID] = mapped_column(ForeignKey("business.support_conversations.id"), index=True)
    channel: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(12), default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    payload_json: Mapped[dict] = mapped_column(JSONB)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_error: Mapped[str | None] = mapped_column(String(64))
    provider_ref: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
