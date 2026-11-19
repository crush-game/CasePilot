"""P05 版本化文档、入库任务与可重建 BM25 快照；仅新增知识表。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0003_knowledge'
down_revision = '0002_runtime'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('kb_index_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('version', sa.BigInteger(), nullable=False),
    sa.Column('snapshot_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('snapshot_checksum', sa.String(length=64), nullable=False),
    sa.CheckConstraint('id = 1 AND version >= 0', name=op.f('ck_kb_index_state_singleton')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kb_index_state')),
    schema='business'
    )
    op.create_table('kb_documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('doc_key', sa.String(length=120), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('filename', sa.String(length=128), nullable=False),
    sa.Column('source_type', sa.String(length=32), nullable=False),
    sa.Column('data_source', sa.String(length=16), nullable=False),
    sa.Column('retrieval_mode', sa.String(length=16), nullable=False),
    sa.Column('product_scope', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('firmware_versions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('regions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('channels', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
    sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('checksum', sa.String(length=64), nullable=False),
    sa.Column('original_bytes', sa.LargeBinary(), nullable=False),
    sa.Column('index_version', sa.BigInteger(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('audit_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("data_source = 'mock' AND retrieval_mode = 'bm25'", name=op.f('ck_kb_documents_mode')),
    sa.CheckConstraint("status IN ('pending','active','failed','archived','superseded')", name=op.f('ck_kb_documents_status')),
    sa.CheckConstraint('effective_to IS NULL OR effective_from IS NULL OR effective_to > effective_from', name=op.f('ck_kb_documents_effective_range')),
    sa.CheckConstraint('version >= 1 AND revision >= 1', name=op.f('ck_kb_documents_versions')),
    sa.ForeignKeyConstraint(['created_by'], ['business.app_users.id'], name=op.f('fk_kb_documents_created_by_app_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kb_documents')),
    sa.UniqueConstraint('doc_key', 'version', name='uq_kb_documents_key_version'),
    schema='business'
    )
    op.create_index('ix_kb_documents_product_scope', 'kb_documents', ['product_scope'], unique=False, schema='business', postgresql_using='gin')
    op.create_index('ix_kb_documents_status_created', 'kb_documents', ['status', 'created_at', 'id'], unique=False, schema='business')
    op.create_index('uq_kb_documents_active_key', 'kb_documents', ['doc_key'], unique=True, schema='business', postgresql_where=sa.text("status = 'active'"))
    op.create_table('ingestion_jobs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('stage', sa.String(length=32), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('revision', sa.Integer(), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('retryable', sa.Boolean(), nullable=False),
    sa.Column('lease_token', sa.Uuid(), nullable=True),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('index_version', sa.BigInteger(), nullable=True),
    sa.Column('history_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('queued','running','succeeded','failed','cancelled')", name=op.f('ck_ingestion_jobs_status')),
    sa.CheckConstraint('attempt >= 0 AND revision >= 1', name=op.f('ck_ingestion_jobs_versions')),
    sa.ForeignKeyConstraint(['document_id'], ['business.kb_documents.id'], name=op.f('fk_ingestion_jobs_document_id_kb_documents')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ingestion_jobs')),
    sa.UniqueConstraint('document_id', name='uq_ingestion_jobs_document'),
    schema='business'
    )
    op.create_index('ix_ingestion_jobs_status_created', 'ingestion_jobs', ['status', 'created_at', 'id'], unique=False, schema='business')
    op.create_table('kb_chunks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('ordinal', sa.Integer(), nullable=False),
    sa.Column('heading_path', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('start_line', sa.Integer(), nullable=False),
    sa.Column('end_line', sa.Integer(), nullable=False),
    sa.Column('content_hash', sa.String(length=64), nullable=False),
    sa.Column('metadata_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint('ordinal >= 0 AND start_line >= 1 AND end_line >= start_line', name=op.f('ck_kb_chunks_positions')),
    sa.ForeignKeyConstraint(['document_id'], ['business.kb_documents.id'], name=op.f('fk_kb_chunks_document_id_kb_documents')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_kb_chunks')),
    sa.UniqueConstraint('document_id', 'ordinal', name='uq_kb_chunks_document_ordinal'),
    schema='business'
    )
    op.create_index(op.f('ix_kb_chunks_document_id'), 'kb_chunks', ['document_id'], unique=False, schema='business')


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
