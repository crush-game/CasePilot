"""P09 结案结果来源与经验候选审阅。"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_experiences"
down_revision = "0005_faults"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_ticket_id", sa.Uuid(), nullable=False),
        sa.Column("source_run_id", sa.Uuid(), nullable=True),
        sa.Column("source_action_id", sa.Uuid(), nullable=False),
        sa.Column("result_version", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("content_json", JSONB(), nullable=False),
        sa.Column("review_json", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiences")),
        sa.ForeignKeyConstraint(["source_ticket_id"], ["business.tickets.id"], name=op.f("fk_experiences_source_ticket_id_tickets")),
        sa.ForeignKeyConstraint(["source_action_id"], ["business.audit_events.action_id"], name=op.f("fk_experiences_source_action_id_audit_events"),
                                deferrable=True, initially="DEFERRED"),
        sa.ForeignKeyConstraint(["source_run_id", "source_ticket_id"], ["business.runs.id", "business.runs.ticket_id"],
                                name="fk_experiences_run_ticket"),
        sa.UniqueConstraint("source_action_id", name=op.f("uq_experiences_source_action_id")),
        sa.UniqueConstraint("source_ticket_id", "result_version", name="uq_experiences_result"),
        sa.CheckConstraint("status IN ('queued','candidate','reviewed','archived')", name=op.f("ck_experiences_status")),
        sa.CheckConstraint("version >= 1 AND result_version >= 1", name=op.f("ck_experiences_versions")),
        schema="business",
    )
    op.create_index("ix_experiences_status_created", "experiences", ["status", "created_at", "id"], schema="business")


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
