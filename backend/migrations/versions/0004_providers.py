"""P06 调用预算/审计、向量 profile 和索引构建；兼容已有 BM25 数据。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = '0004_providers'
down_revision = '0003_knowledge'
branch_labels = None
depends_on = None


def upgrade():
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.drop_constraint(op.f('ck_kb_documents_mode'), 'kb_documents', schema='business', type_='check')
    op.create_check_constraint(op.f('ck_kb_documents_mode'), 'kb_documents',
                               "data_source = 'mock' AND retrieval_mode IN ('bm25','hybrid')", schema='business')
    op.create_table('embedding_profiles',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('fingerprint', sa.String(length=64), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('inference_mode', sa.String(length=16), nullable=False),
    sa.Column('config_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_embedding_profiles')),
    sa.UniqueConstraint('fingerprint', name=op.f('uq_embedding_profiles_fingerprint')),
    sa.UniqueConstraint('id', 'dimensions', name='uq_embedding_profiles_id_dimensions'),
    schema='business'
    )
    op.create_table('provider_budgets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('scope', sa.String(length=120), nullable=False),
    sa.Column('max_calls', sa.Integer(), nullable=False),
    sa.Column('max_tokens', sa.BigInteger(), nullable=False),
    sa.Column('max_cost', sa.Numeric(precision=18, scale=8), nullable=False),
    sa.Column('currency', sa.String(length=8), nullable=False),
    sa.Column('calls_used', sa.Integer(), nullable=False),
    sa.Column('tokens_used', sa.BigInteger(), nullable=False),
    sa.Column('exposure_cost', sa.Numeric(precision=18, scale=8), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('max_calls > 0 AND max_tokens > 0 AND max_cost > 0 AND calls_used >= 0 AND tokens_used >= 0 AND exposure_cost >= 0', name=op.f('ck_provider_budgets_limits')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_provider_budgets')),
    schema='business'
    )
    op.create_table('kb_index_builds',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('budget_id', sa.Uuid(), nullable=False),
    sa.Column('base_version', sa.BigInteger(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('index_version', sa.BigInteger(), nullable=True),
    sa.Column('chunk_count', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['budget_id'], ['business.provider_budgets.id'], name=op.f('fk_kb_index_builds_budget_id_provider_budgets')),
    sa.ForeignKeyConstraint(['profile_id'], ['business.embedding_profiles.id'], name=op.f('fk_kb_index_builds_profile_id_embedding_profiles')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kb_index_builds')),
    schema='business'
    )
    op.create_table('provider_calls',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('budget_id', sa.Uuid(), nullable=False),
    sa.Column('operation', sa.String(length=32), nullable=False),
    sa.Column('inference_mode', sa.String(length=16), nullable=False),
    sa.Column('profile_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('response_hash', sa.String(length=64), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('reserved_tokens', sa.BigInteger(), nullable=False),
    sa.Column('reserved_cost', sa.Numeric(precision=18, scale=8), nullable=False),
    sa.Column('usage_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('provider_request_id', sa.String(length=200), nullable=True),
    sa.Column('duration_ms', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['budget_id'], ['business.provider_budgets.id'], name=op.f('fk_provider_calls_budget_id_provider_budgets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_provider_calls')),
    schema='business'
    )
    op.create_index(op.f('ix_provider_calls_budget_id'), 'provider_calls', ['budget_id'], unique=False, schema='business')
    op.create_table('kb_embeddings',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('chunk_id', sa.Uuid(), nullable=False),
    sa.Column('profile_id', sa.Uuid(), nullable=False),
    sa.Column('dimensions', sa.Integer(), nullable=False),
    sa.Column('embedding', Vector(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('provider_call_id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('vector_dims(embedding) = dimensions', name=op.f('ck_kb_embeddings_dimensions')),
    sa.ForeignKeyConstraint(['chunk_id'], ['business.kb_chunks.id'], name=op.f('fk_kb_embeddings_chunk_id_kb_chunks')),
    sa.ForeignKeyConstraint(['profile_id', 'dimensions'], ['business.embedding_profiles.id', 'business.embedding_profiles.dimensions'], name='fk_kb_embeddings_profile_dimensions'),
    sa.ForeignKeyConstraint(['provider_call_id'], ['business.provider_calls.id'], name=op.f('fk_kb_embeddings_provider_call_id_provider_calls')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kb_embeddings')),
    sa.UniqueConstraint('chunk_id', 'profile_id', name='uq_kb_embeddings_chunk_profile'),
    schema='business'
    )
    op.add_column('kb_index_state', sa.Column('active_profile_id', sa.Uuid(), nullable=True), schema='business')
    op.create_foreign_key(op.f('fk_kb_index_state_active_profile_id_embedding_profiles'), 'kb_index_state', 'embedding_profiles', ['active_profile_id'], ['id'], source_schema='business', referent_schema='business')


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
