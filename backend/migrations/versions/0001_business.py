"""P01 业务数据与账号：冻结的初始迁移。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_business"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 初始表结构固定在此迁移中，不导入运行时模型。
    op.create_table('app_users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('login', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=256), nullable=False),
    sa.Column('role', sa.String(length=32), nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("role IN ('business', 'knowledge_admin')", name=op.f('ck_app_users_role')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_app_users')),
    sa.UniqueConstraint('login'),
    schema='business'
    )
    op.create_table('auth_sessions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['business.app_users.id'], name=op.f('fk_auth_sessions_user_id_app_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_auth_sessions')),
    sa.UniqueConstraint('token_hash'),
    schema='business'
    )
    op.create_table('idempotency_records',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('operation', sa.String(length=128), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('response_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['business.app_users.id'], name=op.f('fk_idempotency_records_actor_id_app_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_idempotency_records')),
    sa.UniqueConstraint('actor_id', 'operation', 'key', name='uq_idempotency_scope'),
    schema='business'
    )
    op.create_table('tickets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_no', sa.String(length=48), nullable=False),
    sa.Column('source', sa.String(length=32), nullable=False),
    sa.Column('data_source', sa.String(length=16), nullable=False),
    sa.Column('customer_email', sa.String(length=254), nullable=False),
    sa.Column('feedback_text', sa.Text(), nullable=False),
    sa.Column('device_ref', sa.String(length=128), nullable=True),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('occurred_at_original', sa.String(length=64), nullable=True),
    sa.Column('occurred_at_precision', sa.String(length=16), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('priority', sa.String(length=16), nullable=False),
    sa.Column('assignee_id', sa.Uuid(), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('active_run_id', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("priority IN ('low', 'normal', 'high', 'urgent')", name=op.f('ck_tickets_priority')),
    sa.CheckConstraint("status IN ('QUEUED', 'RUNNING', 'WAITING_HUMAN', 'WAITING_CUSTOMER', 'PENDING_CONFIRMATION', 'RESOLVED', 'CLOSED_UNRESOLVED')", name=op.f('ck_tickets_status')),
    sa.CheckConstraint('version >= 1', name=op.f('ck_tickets_version')),
    sa.ForeignKeyConstraint(['assignee_id'], ['business.app_users.id'], name=op.f('fk_tickets_assignee_id_app_users')),
    sa.ForeignKeyConstraint(['created_by'], ['business.app_users.id'], name=op.f('fk_tickets_created_by_app_users')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tickets')),
    sa.UniqueConstraint('id', 'active_run_id', name='uq_tickets_id_active_run'),
    sa.UniqueConstraint('ticket_no'),
    schema='business'
    )
    op.create_table('audit_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('action_id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('expected_version', sa.Integer(), nullable=True),
    sa.Column('operation', sa.String(length=64), nullable=False),
    sa.Column('patch', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['business.app_users.id'], name=op.f('fk_audit_events_actor_id_app_users')),
    sa.ForeignKeyConstraint(['ticket_id'], ['business.tickets.id'], name=op.f('fk_audit_events_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events')),
    sa.UniqueConstraint('action_id'),
    schema='business'
    )
    op.create_table('runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('thread_id', sa.String(length=64), nullable=False),
    sa.Column('graph_version', sa.String(length=64), nullable=False),
    sa.Column('case_version', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('checkpoint_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('budget_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('stop_reason', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('queued', 'running', 'paused', 'succeeded', 'failed', 'superseded')", name=op.f('ck_runs_status')),
    sa.CheckConstraint('case_version >= 1', name=op.f('ck_runs_case_version')),
    sa.ForeignKeyConstraint(['ticket_id'], ['business.tickets.id'], name=op.f('fk_runs_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_runs')),
    sa.UniqueConstraint('id', 'ticket_id', name='uq_runs_id_ticket'),
    sa.UniqueConstraint('thread_id'),
    schema='business'
    )
    op.create_table('ticket_facts',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('field', sa.String(length=64), nullable=False),
    sa.Column('value_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('source_type', sa.String(length=32), nullable=False),
    sa.Column('source_ref', sa.String(length=128), nullable=False),
    sa.Column('fact_version', sa.Integer(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['business.app_users.id'], name=op.f('fk_ticket_facts_actor_id_app_users')),
    sa.ForeignKeyConstraint(['ticket_id'], ['business.tickets.id'], name=op.f('fk_ticket_facts_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ticket_facts')),
    sa.UniqueConstraint('ticket_id', 'field', 'fact_version', name='uq_facts_version'),
    schema='business'
    )
    op.create_table('case_snapshots',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('case_version', sa.Integer(), nullable=False),
    sa.Column('state_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('checksum', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_case_snapshots_run_id_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_case_snapshots')),
    sa.UniqueConstraint('run_id', 'case_version', name='uq_snapshots_version'),
    schema='business'
    )
    op.create_table('execution_tasks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('action_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('available_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('lease_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('lease_token', sa.Uuid(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')", name=op.f('ck_execution_tasks_status')),
    sa.CheckConstraint('attempt >= 0', name=op.f('ck_execution_tasks_attempt')),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_execution_tasks_run_id_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_execution_tasks')),
    sa.UniqueConstraint('run_id', 'kind', 'action_id', name='uq_tasks_logical_action'),
    schema='business'
    )
    op.create_table('ticket_events',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=True),
    sa.Column('event_type', sa.String(length=64), nullable=False),
    sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_ticket_events_run_id_runs')),
    sa.ForeignKeyConstraint(['ticket_id'], ['business.tickets.id'], name=op.f('fk_ticket_events_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_ticket_events')),
    schema='business'
    )
    op.create_index(op.f('ix_auth_sessions_expires_at'), 'auth_sessions', ['expires_at'], unique=False, schema='business')
    op.create_index(op.f('ix_auth_sessions_user_id'), 'auth_sessions', ['user_id'], unique=False, schema='business')
    op.create_index('ix_tickets_created_id', 'tickets', ['created_at', 'id'], unique=False, schema='business')
    op.create_index('ix_tickets_status_assignee_created', 'tickets', ['status', 'assignee_id', 'created_at'], unique=False, schema='business')
    op.create_index(op.f('ix_audit_events_ticket_id'), 'audit_events', ['ticket_id'], unique=False, schema='business')
    op.create_index('uq_runs_active_ticket', 'runs', ['ticket_id'], unique=True, schema='business', postgresql_where=sa.text("status IN ('queued','running','paused')"))
    op.create_index('ix_tasks_status_available', 'execution_tasks', ['status', 'available_at'], unique=False, schema='business')
    op.create_index('ix_events_ticket_id', 'ticket_events', ['ticket_id', 'id'], unique=False, schema='business')
    op.create_foreign_key('fk_tickets_active_run', 'tickets', 'runs', ['active_run_id', 'id'], ['id', 'ticket_id'], source_schema='business', referent_schema='business', initially='DEFERRED', deferrable=True, use_alter=True)


def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
