"""P13 经验发布版本、撤回与适用范围。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0009_releases"
down_revision = "0008_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("experience_publications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("experience_id", sa.Uuid(), sa.ForeignKey("business.experiences.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("problem_key", sa.String(64), nullable=False),
        sa.Column("scope_json", JSONB(), nullable=False),
        sa.Column("content_json", JSONB(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("withdrawal_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("experience_id", "revision", name="uq_experience_publications_revision"),
        sa.CheckConstraint("status IN ('active','withdrawn') AND revision >= 1", name=op.f("ck_experience_publications_status_revision")),
        schema="business")
    op.create_index("uq_experience_publications_active", "experience_publications", ["experience_id"], unique=True,
                    schema="business", postgresql_where=sa.text("status = 'active'"))
    op.create_index("ix_experience_publications_problem", "experience_publications", ["problem_key"],
                    schema="business", postgresql_where=sa.text("status = 'active'"))


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
