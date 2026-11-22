"""P17 结案会话快照、规则版本、质检批次和结果。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0011_quality"
down_revision = "0010_support_intake"
branch_labels = None
depends_on = None


def upgrade():
    rules = op.create_table("quality_rule_sets", sa.Column("version", sa.String(24), primary_key=True),
                            sa.Column("config_json", JSONB(), nullable=False),
                            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
                            schema="business")
    op.bulk_insert(rules, [{"version": "v0.1", "config_json": {
        "deductions": {"business_incomplete": 20, "process_late": 20, "format_missing": 10,
                       "service_dismissive": 30, "operation_model": 5},
        "caps": {"business": 40, "process": 30, "format": 10, "service": 40, "operation": 30},
        "follow_up_minutes": 480,
        "require_greeting": False,
    }}])
    op.create_table("quality_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("business.tickets.id"), nullable=False, unique=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("business.support_conversations.id"), nullable=False),
        sa.Column("case_version", sa.Integer(), nullable=False),
        sa.Column("rule_version", sa.String(24), sa.ForeignKey("business.quality_rule_sets.version"), nullable=False),
        sa.Column("data_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="business")
    op.create_table("quality_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("batch_key", sa.String(80), nullable=False, unique=True),
        sa.Column("ticket_id", sa.Uuid(), sa.ForeignKey("business.tickets.id")),
        sa.Column("random_pct", sa.Integer(), nullable=False),
        sa.Column("max_calls", sa.Integer(), nullable=False),
        sa.Column("calls_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("selection_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), schema="business")
    op.create_table("quality_assessments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("business.quality_snapshots.id"), nullable=False),
        sa.Column("subject_id", sa.Uuid(), sa.ForeignKey("business.app_users.id"), nullable=False),
        sa.Column("rule_version", sa.String(24), sa.ForeignKey("business.quality_rule_sets.version"), nullable=False),
        sa.Column("batch_id", sa.Uuid(), sa.ForeignKey("business.quality_batches.id")),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("result_json", JSONB(), nullable=False),
        sa.Column("history_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("snapshot_id", "subject_id", "rule_version", name="uq_quality_assessments_subject_rule"),
        sa.CheckConstraint("status IN ('queued','screened','ai_queued','pending_review','finalized','appealed','insufficient')",
                           name=op.f("ck_quality_assessments_status")), schema="business")
    op.create_index("ix_quality_assessments_status", "quality_assessments", ["status", "created_at", "id"], schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
