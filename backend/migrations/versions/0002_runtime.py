"""P02 Worker 与人工恢复：仅新增表和兼容字段。"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_runtime"
down_revision = "0001_business"
branch_labels = None
depends_on = None


def upgrade():
    # 新增运行记录、人工待办及兼容默认值。
    op.create_table('human_tasks',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('ticket_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('pause_key', sa.String(length=128), nullable=False),
    sa.Column('reason_code', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('assignee_id', sa.Uuid(), nullable=True),
    sa.Column('checkpoint_ref', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('unclaimed', 'claimed', 'resuming', 'completed', 'cancelled')", name=op.f('ck_human_tasks_status')),
    sa.ForeignKeyConstraint(['assignee_id'], ['business.app_users.id'], name=op.f('fk_human_tasks_assignee_id_app_users')),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_human_tasks_run_id_runs')),
    sa.ForeignKeyConstraint(['ticket_id'], ['business.tickets.id'], name=op.f('fk_human_tasks_ticket_id_tickets')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_human_tasks')),
    sa.UniqueConstraint('run_id', 'pause_key', name='uq_human_tasks_pause'),
    schema='business'
    )
    op.create_index('ix_human_tasks_status_created', 'human_tasks', ['status', 'created_at', 'id'], unique=False, schema='business')
    op.create_index('uq_human_tasks_open_ticket', 'human_tasks', ['ticket_id'], unique=True, schema='business', postgresql_where=sa.text("status IN ('unclaimed','claimed','resuming')"))
    op.create_table('node_runs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('node_name', sa.String(length=64), nullable=False),
    sa.Column('logical_step_id', sa.String(length=160), nullable=False),
    sa.Column('attempt', sa.Integer(), nullable=False),
    sa.Column('input_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('output_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('model_version', sa.String(length=64), nullable=True),
    sa.Column('usage_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('duration_ms', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_node_runs_run_id_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_node_runs')),
    sa.UniqueConstraint('run_id', 'logical_step_id', 'attempt', name='uq_node_runs_step'),
    schema='business'
    )
    op.create_index(op.f('ix_node_runs_run_id'), 'node_runs', ['run_id'], unique=False, schema='business')
    op.create_table('tool_executions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('logical_action_id', sa.Uuid(), nullable=False),
    sa.Column('tool_name', sa.String(length=64), nullable=False),
    sa.Column('args_hash', sa.String(length=64), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('result_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('error_code', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_tool_executions_run_id_runs')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tool_executions')),
    sa.UniqueConstraint('run_id', 'logical_action_id', name='uq_tool_executions_action'),
    schema='business'
    )
    op.create_table('human_actions',
    sa.Column('action_id', sa.Uuid(), nullable=False),
    sa.Column('human_task_id', sa.Uuid(), nullable=False),
    sa.Column('run_id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=False),
    sa.Column('expected_version', sa.Integer(), nullable=False),
    sa.Column('request_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consumed_checkpoint', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['business.app_users.id'], name=op.f('fk_human_actions_actor_id_app_users')),
    sa.ForeignKeyConstraint(['human_task_id'], ['business.human_tasks.id'], name=op.f('fk_human_actions_human_task_id_human_tasks')),
    sa.ForeignKeyConstraint(['run_id'], ['business.runs.id'], name=op.f('fk_human_actions_run_id_runs')),
    sa.PrimaryKeyConstraint('action_id', name=op.f('pk_human_actions')),
    schema='business'
    )
    op.create_index(op.f('ix_human_actions_run_id'), 'human_actions', ['run_id'], unique=False, schema='business')
    op.add_column('execution_tasks', sa.Column('payload_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False), schema='business')
    op.add_column('runs', sa.Column('cancel_requested', sa.Boolean(), server_default=sa.text('false'), nullable=False), schema='business')
    op.add_column('tickets', sa.Column('solution_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False), schema='business')
    op.add_column('tickets', sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False), schema='business')

def downgrade():
    raise RuntimeError("禁止自动破坏性降级；请先设计兼容回滚方案")
