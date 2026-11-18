from contextlib import contextmanager

import psycopg
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row

from app.config import get_settings


@contextmanager
def checkpoint_connection(database_url=None):
    with psycopg.connect(
        database_url or get_settings().database_url.get_secret_value(), autocommit=True,
        prepare_threshold=0, row_factory=dict_row, connect_timeout=3,
    ) as connection:
        connection.execute("SET search_path TO checkpoints, public")
        yield connection


def setup_checkpoints(database_url=None):
    with checkpoint_connection(database_url) as connection:
        connection.execute("SELECT pg_advisory_lock(671902001)")
        connection.execute("CREATE SCHEMA IF NOT EXISTS checkpoints")
        PostgresSaver(connection).setup()


def try_run_lock(connection, run_id):
    return connection.execute(
        "SELECT pg_try_advisory_lock(hashtextextended(%s, 0)) AS acquired", (str(run_id),)
    ).fetchone()["acquired"]
