import json
import os
import subprocess
import sys
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import get_settings
from app.main import app


pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def database_url():
    url = os.environ.get("AFTERSALES_TEST_DATABASE_URL")
    if not url:
        pytest.fail("验收必须设置 AFTERSALES_TEST_DATABASE_URL，不能跳过 PostgreSQL")
    with psycopg.connect(url, autocommit=True) as conn:
        assert conn.info.dbname == "aftersales_test", "禁止向其他数据库运行试验"
        assert conn.info.server_version // 10000 == 17
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    return url


def probe(action, thread_id):
    result = subprocess.run(
        [sys.executable, "-m", "app.agents.graphs.compatibility", action, "--thread-id", thread_id],
        check=True, capture_output=True, text=True, timeout=45,
    )
    return json.loads(result.stdout)


def test_vector_query(database_url):
    with psycopg.connect(database_url) as conn:
        # 仅使用本连接临时表，不清空开发数据。
        conn.execute("CREATE TEMP TABLE p00_vectors (id integer, embedding vector(3))")
        conn.execute("INSERT INTO p00_vectors VALUES (1, '[1,0,0]'), (2, '[0,1,0]')")
        row = conn.execute(
            "SELECT id, embedding <-> '[1,0,0]'::vector AS distance "
            "FROM p00_vectors ORDER BY distance LIMIT 1"
        ).fetchone()
        assert row == (1, 0.0)


def test_sqlalchemy_psycopg_connection(database_url):
    engine = create_engine(database_url.replace("postgresql://", "postgresql+psycopg://", 1))
    try:
        with engine.connect() as conn:
            assert conn.execute(text("SELECT current_database()")).scalar_one() == "aftersales_test"
    finally:
        engine.dispose()


def test_api_ready_with_vector_database(database_url, monkeypatch):
    monkeypatch.setenv("AFTERSALES_DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        with TestClient(app) as client:
            response = client.get("/health/ready")
            assert response.status_code == 200
            assert response.json() == {"status": "ok", "data_source": "mock"}
    finally:
        get_settings.cache_clear()


def test_interrupt_survives_process_exit(database_url):
    thread_id = str(uuid4())
    probe("setup", thread_id)
    paused = probe("pause", thread_id)
    assert paused["interrupted"] is True
    assert paused["next"] == ["human_interrupt"]
    resumed = probe("resume", thread_id)
    assert paused["pid"] != resumed["pid"]
    assert resumed["values"]["answer"] == "DEMO-01"
    assert resumed["values"]["complete"] is True
    assert resumed["interrupted"] is False
    assert resumed["next"] == []
    assert paused["checkpoint_id"] != resumed["checkpoint_id"]


def test_run_lock_exclusion_and_connection_release(database_url):
    run_id = str(uuid4())
    with psycopg.connect(database_url, autocommit=True) as first:
        with psycopg.connect(database_url, autocommit=True) as second:
            sql = "SELECT pg_try_advisory_lock(hashtextextended(%s, 0))"
            assert first.execute(sql, (run_id,)).fetchone()[0] is True
            assert second.execute(sql, (run_id,)).fetchone()[0] is False
            first.close()
            assert second.execute(sql, (run_id,)).fetchone()[0] is True
