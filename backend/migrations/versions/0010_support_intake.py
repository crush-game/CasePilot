"""P15 保存会话受理版本、客户操作及正式回复作者。"""
from alembic import op
import sqlalchemy as sa


revision = "0010_support_intake"
down_revision = "0009_releases"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("support_conversations",
                  sa.Column("flow_version", sa.String(16), nullable=False, server_default="support-v1"),
                  schema="business")
    op.create_check_constraint(op.f("ck_support_conversations_flow_version"), "support_conversations",
                               "flow_version IN ('support-v1','support-v2')", schema="business")
    op.add_column("support_turns", sa.Column("request_action", sa.String(24)), schema="business")
    op.add_column("support_deliveries", sa.Column("reply_author_id", sa.Uuid()), schema="business")
    op.create_foreign_key(op.f("fk_support_deliveries_reply_author_id_app_users"),
                          "support_deliveries", "app_users", ["reply_author_id"], ["id"],
                          source_schema="business", referent_schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
