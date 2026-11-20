"""P08 工单隔离的原始附件与脱敏日志证据。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_faults"
down_revision = "0004_providers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("log_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("feedback_ref", sa.String(120), nullable=False),
        sa.Column("source_kind", sa.String(24), nullable=False),
        sa.Column("data_source", sa.String(16), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("context_hash", sa.String(64), nullable=False),
        sa.Column("media_type", sa.String(60), nullable=False),
        sa.Column("original_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("metadata_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_artifacts")),
        sa.ForeignKeyConstraint(["run_id", "ticket_id"], ["business.runs.id", "business.runs.ticket_id"], name="fk_log_artifacts_run_ticket"),
        sa.UniqueConstraint("id", "run_id", "ticket_id", name="uq_log_artifacts_owner"),
        sa.UniqueConstraint("run_id", "feedback_ref", "source_kind", name="uq_log_artifacts_source"),
        sa.CheckConstraint("source_kind IN ('detailed_log','telemetry') AND data_source = 'mock'", name=op.f("ck_log_artifacts_mode")), schema="business")
    op.create_table("log_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("artifact_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=False),
        sa.Column("member_name", sa.String(200), nullable=False),
        sa.Column("line_number", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("domain", sa.String(30), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_log_evidence")),
        sa.ForeignKeyConstraint(["artifact_id", "run_id", "ticket_id"],
            ["business.log_artifacts.id", "business.log_artifacts.run_id", "business.log_artifacts.ticket_id"], name="fk_log_evidence_artifact_owner"),
        sa.UniqueConstraint("artifact_id", "member_name", "line_number", name="uq_log_evidence_line"),
        sa.CheckConstraint("line_number > 0", name=op.f("ck_log_evidence_line")), schema="business")
    op.create_index("ix_log_evidence_run_time", "log_evidence", ["run_id", "occurred_at"], schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
