"""P11 消费者账号、会话与持久回复。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_support"
down_revision = "0006_experiences"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint(op.f("ck_app_users_role"), "app_users", schema="business", type_="check")
    op.create_check_constraint(op.f("ck_app_users_role"), "app_users",
        "role IN ('business','knowledge_admin','consumer')", schema="business")
    op.create_table("support_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("ticket_id", sa.Uuid(), nullable=True),
        sa.Column("context_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_conversations")),
        sa.ForeignKeyConstraint(["owner_id"], ["business.app_users.id"], name=op.f("fk_support_conversations_owner_id_app_users")),
        sa.ForeignKeyConstraint(["ticket_id"], ["business.tickets.id"], name=op.f("fk_support_conversations_ticket_id_tickets")),
        sa.UniqueConstraint("ticket_id", name=op.f("uq_support_conversations_ticket_id")), schema="business")
    op.create_index("ix_support_conversations_owner_created", "support_conversations", ["owner_id", "created_at", "id"], schema="business")
    op.create_table("support_turns",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("reply_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_support_turns")),
        sa.ForeignKeyConstraint(["conversation_id"], ["business.support_conversations.id"],
            name=op.f("fk_support_turns_conversation_id_support_conversations")), schema="business")
    op.create_index("ix_support_turns_conversation_id", "support_turns", ["conversation_id", "id"], schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
