from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_health_does_not_require_a_model_or_database_for_liveness(monkeypatch):
    monkeypatch.setenv("AFTERSALES_DATABASE_URL", "postgresql://localhost/p00_unused")
    get_settings.cache_clear()
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        with patch("app.main.psycopg.connect", side_effect=psycopg.OperationalError):
            assert client.get("/health/ready").status_code == 503
    get_settings.cache_clear()
