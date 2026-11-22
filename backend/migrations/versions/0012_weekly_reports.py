"""P18 周报版本、投递尝试和质检知识缺口。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0012_weekly_reports"
down_revision = "0011_quality"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("weekly_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("definition_version", sa.String(24), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metrics_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("week_start", "revision", name="uq_weekly_reports_week_revision"), schema="business")
    op.create_table("weekly_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("report_id", sa.Uuid(), sa.ForeignKey("business.weekly_reports.id"), nullable=False),
        sa.Column("group_key", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("receipt", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("report_id", "group_key", name="uq_weekly_deliveries_report_group"),
        sa.CheckConstraint("status IN ('queued','sending','sent','failed','unknown')",
                           name=op.f("ck_weekly_deliveries_status")), schema="business")
    op.create_index("ix_weekly_deliveries_ready", "weekly_deliveries", ["status", "available_at", "id"], schema="business")
    op.create_table("quality_knowledge_gaps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assessment_id", sa.Uuid(), sa.ForeignKey("business.quality_assessments.id"), nullable=False),
        sa.Column("rule_id", sa.String(40), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("business.app_users.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("evidence_json", JSONB(), nullable=False),
        sa.Column("resolution_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("assessment_id", "rule_id", name="uq_quality_gaps_assessment_rule"),
        sa.CheckConstraint("status IN ('pending','confirmed','dismissed')",
                           name=op.f("ck_quality_knowledge_gaps_status")), schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
