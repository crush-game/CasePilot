from alembic import context
from sqlalchemy import text

from app.repositories.database import get_engine
from app.repositories.models import Base, SCHEMA


def include_name(name, type_, parent_names):
    if type_ == "schema":
        return name == SCHEMA
    if type_ == "table":
        return parent_names.get("schema_name") == SCHEMA
    return True


def migrate(connection):
    # 迁移串行执行；不触碰 checkpoints schema 和官方 Saver 表。
    connection.execute(text("SELECT pg_advisory_xact_lock(671901001)"))
    connection.execute(text("CREATE SCHEMA IF NOT EXISTS business"))
    context.configure(
        connection=connection, target_metadata=Base.metadata, include_schemas=True,
        version_table_schema=SCHEMA, compare_type=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("本项目迁移需要 PostgreSQL 在线连接，请使用本地管理命令")
connection = context.config.attributes.get("connection")
if connection is not None:
    migrate(connection)
else:
    with get_engine().begin() as connection:
        migrate(connection)
