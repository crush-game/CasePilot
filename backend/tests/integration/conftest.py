import os
import secrets
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import Role
from app.main import app
from app.manage import create_user, upgrade_database
from app.repositories.database import get_engine
from app.workers.checkpoints import setup_checkpoints


@pytest.fixture(scope="session", autouse=True)
def test_engine():
    raw_url = os.environ.get("AFTERSALES_TEST_DATABASE_URL")
    if not raw_url:
        pytest.fail("必须配置独立 PostgreSQL 测试库")
    url = make_url(raw_url)
    assert url.database == "aftersales_test"
    assert url.host in {"localhost", "127.0.0.1"}
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    upgrade_database(engine)
    setup_checkpoints(raw_url)
    yield engine
    engine.dispose()


@pytest.fixture
def account_factory(test_engine):
    def create(role=Role.BUSINESS):
        name, password = f"test_{uuid4().hex}", secrets.token_urlsafe(24)
        with Session(test_engine, expire_on_commit=False) as db:
            user = create_user(db, name, password, role)
        return user, password
    return create


@pytest.fixture
def api(test_engine, account_factory, monkeypatch):
    monkeypatch.setenv("AFTERSALES_DATABASE_URL", os.environ["AFTERSALES_TEST_DATABASE_URL"])
    get_settings.cache_clear()
    get_engine.cache_clear()
    user, password = account_factory()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post("/api/v1/auth/login", json={"login": user.login, "password": password})
        assert response.status_code == 200
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client, user, password
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()
