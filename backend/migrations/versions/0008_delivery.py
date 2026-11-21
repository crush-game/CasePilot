"""P12 模拟渠道、入站事件与事务发送队列。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0008_delivery"
down_revision = "0007_support"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("channel_threads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sender_id", sa.Uuid(), sa.ForeignKey("business.app_users.id"), nullable=False),
        sa.Column("external_ref", sa.String(120), nullable=False),
        sa.Column("issue_ref", sa.String(120), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("business.support_conversations.id"), unique=True),
        sa.Column("reply_target", sa.String(120), nullable=False),
        sa.Column("latest_sequence", sa.Integer(), nullable=False),
        sa.UniqueConstraint("sender_id", "external_ref", "issue_ref", name="uq_channel_threads_issue"), schema="business")
    op.create_table("channel_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("thread_id", sa.Uuid(), sa.ForeignKey("business.channel_threads.id")),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("event_json", JSONB, nullable=False),
        sa.Column("response_json", JSONB, nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), schema="business")
    op.create_table("support_deliveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("business.support_conversations.id"), nullable=False),
        sa.Column("channel", sa.String(12), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("payload_json", JSONB, nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error", sa.String(64)),
        sa.Column("provider_ref", sa.String(160)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status IN ('queued','delivered','failed')", name=op.f("ck_support_deliveries_status")),
        sa.CheckConstraint("channel IN ('app','mock')", name=op.f("ck_support_deliveries_channel")),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name=op.f("ck_support_deliveries_attempts")), schema="business")
    op.create_index("ix_support_deliveries_eligible", "support_deliveries", ["status", "available_at", "id"], schema="business")
    op.create_index("ix_support_deliveries_conversation_id", "support_deliveries", ["conversation_id"], schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
