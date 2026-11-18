from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine, event, func, inspect, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.main import app
from app.manage import migration_config, upgrade_database
from app.repositories.database import get_engine
from app.repositories.models import (
    AppUser, AuditEvent, AuthSession, CaseSnapshot, ExecutionTask, IdempotencyRecord,
    Run, SCHEMA_VERSION, Ticket, TicketEvent, TicketFact,
)


pytestmark = pytest.mark.integration
PAYLOAD = {
    "customer_email": "demo@example.test", "feedback_text": "升级后反复断连",
    "device_ref": "DEMO-01", "occurred_at": "2026-11-18T10:00:00+08:00",
    "occurred_at_precision": "minute",
}


def create_ticket(client, key=None, **changes):
    return client.post("/api/v1/tickets", json={**PAYLOAD, **changes}, headers={"Idempotency-Key": key or str(uuid4())})


def test_empty_database_can_migrate_and_upgrade_twice(test_engine):
    # 名称由本测试随机生成；仅清理本测试创建、已核验名称的临时库。
    name = f"aftersales_p01_{uuid4().hex}"
    params = test_engine.url.translate_connect_args(username="user", database="dbname")
    with psycopg.connect(**params, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = create_engine(test_engine.url.set(database=name))
        try:
            assert "business" not in inspect(engine).get_schema_names()
            upgrade_database(engine)
            upgrade_database(engine)
            assert set(inspect(engine).get_table_names(schema="business")) >= {
                "app_users", "auth_sessions", "tickets", "runs", "execution_tasks",
                "case_snapshots", "ticket_events", "audit_events", "idempotency_records",
            }
            with engine.connect() as conn:
                assert conn.exec_driver_sql("SELECT version_num FROM business.alembic_version").scalar_one() == SCHEMA_VERSION
                config = migration_config()
                config.attributes["connection"] = conn
                command.check(config)
        finally:
            engine.dispose()
            assert name.startswith("aftersales_p01_") and len(name) == 47
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def test_login_logout_csrf_and_role_permissions(api, account_factory, test_engine):
    client, user, password = api
    assert client.get("/api/v1/auth/me").json()["login"] == user.login
    with TestClient(app) as anonymous:
        assert anonymous.get("/api/v1/tickets").status_code == 401
        wrong = anonymous.post("/api/v1/auth/login", json={"login": user.login, "password": password + "x"})
        assert wrong.status_code == 401
        assert "password" not in wrong.text
        assert anonymous.post("/api/v1/auth/login", json={"login": user.login, "password": password}, headers={"Origin": "https://untrusted.example"}).status_code == 403
    csrf = client.headers.pop("X-CSRF-Token")
    assert create_ticket(client).status_code == 403
    client.headers["X-CSRF-Token"] = csrf
    assert create_ticket(client).status_code == 202
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401
    knowledge_user, knowledge_password = account_factory(Role.KNOWLEDGE_ADMIN)
    login = client.post("/api/v1/auth/login", json={"login": knowledge_user.login, "password": knowledge_password})
    assert "HttpOnly" in login.headers["set-cookie"]
    assert "SameSite=lax" in login.headers["set-cookie"]
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert client.get("/api/v1/tickets").status_code == 403
    assert create_ticket(client).status_code == 403


def test_expired_and_disabled_accounts_cannot_use_session(api, test_engine):
    client, user, password = api
    with Session(test_engine) as db:
        db.execute(update(AppUser).where(AppUser.id == user.id).values(active=False))
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"login": user.login, "password": password}).status_code == 401
    with Session(test_engine) as db:
        db.execute(update(AppUser).where(AppUser.id == user.id).values(active=True))
        db.execute(update(AuthSession).where(AuthSession.user_id == user.id).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
        db.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_idempotency_keys_are_scoped_to_actor(api, account_factory):
    client, _, _ = api
    key = str(uuid4())
    first = create_ticket(client, key)
    other_user, password = account_factory()
    with TestClient(app) as other:
        logged_in = other.post("/api/v1/auth/login", json={"login": other_user.login, "password": password})
        other.headers["X-CSRF-Token"] = logged_in.json()["csrf_token"]
        second = create_ticket(other, key)
    assert first.status_code == second.status_code == 202
    assert first.json()["ticket_id"] != second.json()["ticket_id"]


def test_relogin_invalidates_old_cookie_and_stores_only_hashes(api, test_engine):
    client, user, password = api
    old_cookies = dict(client.cookies)
    login = client.post("/api/v1/auth/login", json={"login": user.login, "password": password})
    assert login.status_code == 200
    with TestClient(app) as old:
        old.cookies.update(old_cookies)
        assert old.get("/api/v1/auth/me").status_code == 401
    with Session(test_engine) as db:
        auth_session = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        assert auth_session.token_hash != client.cookies["casepilot_session"]
        assert auth_session.csrf_hash != login.json()["csrf_token"]
        assert len(auth_session.token_hash) == len(auth_session.csrf_hash) == 64


def test_create_is_idempotent_atomic_and_preserves_time(api, test_engine):
    client, user, _ = api
    key = str(uuid4())
    first, second = create_ticket(client, key), create_ticket(client, key)
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    result = first.json()
    assert create_ticket(client, key, feedback_text="不同问题").status_code == 409
    ticket_id, run_id = UUID(result["ticket_id"]), UUID(result["run_id"])
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.created_by == user.id)) == 1
        assert db.scalar(select(func.count()).select_from(Run).where(Run.ticket_id == ticket_id)) == 1
        assert db.scalar(select(func.count()).select_from(ExecutionTask).where(ExecutionTask.run_id == run_id)) == 1
        assert db.scalar(select(func.count()).select_from(TicketEvent).where(TicketEvent.ticket_id == ticket_id)) == 1
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.ticket_id == ticket_id)) == 1
        assert db.scalar(select(func.count()).select_from(CaseSnapshot).where(CaseSnapshot.run_id == run_id)) == 1
        assert db.scalar(select(func.count()).select_from(TicketFact).where(TicketFact.ticket_id == ticket_id)) == 4
        run = db.get(Run, run_id)
        assert run.thread_id == str(run_id) and run.status == "queued"
    detail = client.get(f"/api/v1/tickets/{ticket_id}").json()
    assert detail["version"] == 1 and detail["latest_event_id"] > 0
    assert detail["active_run_id"] == str(run_id)
    assert detail["occurred_at_original"].endswith("+08:00")
    assert detail["occurred_at_precision"] == "minute"
    assert datetime.fromisoformat(detail["occurred_at"]).hour == 2
    assert client.get(f"/api/v1/runs/{run_id}").json()["status"] == "queued"


def test_simultaneous_duplicate_create_has_one_ticket_run_task(api, test_engine):
    _, user, password = api
    key, barrier = str(uuid4()), Barrier(4)

    def submit(_):
        with TestClient(app) as client:
            login = client.post("/api/v1/auth/login", json={"login": user.login, "password": password})
            client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
            barrier.wait(timeout=15)
            response = create_ticket(client, key)
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(submit, range(4)))
    assert all(status == 202 for status, _ in results)
    assert all(body == results[0][1] for _, body in results)
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.created_by == user.id)) == 1


def test_failed_creation_rolls_back_idempotency_and_all_business_rows(api, test_engine):
    client, user, _ = api
    key = str(uuid4())

    def inject_failure(conn, cursor, statement, params, context, executemany):
        if statement.startswith("INSERT INTO business.case_snapshots"):
            raise RuntimeError("injected private failure")

    engine = get_engine()
    event.listen(engine, "before_cursor_execute", inject_failure)
    try:
        response = create_ticket(client, key)
        assert response.status_code == 500
        assert "injected" not in response.text
    finally:
        event.remove(engine, "before_cursor_execute", inject_failure)
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.created_by == user.id)) == 0
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord).where(IdempotencyRecord.actor_id == user.id)) == 0
    assert create_ticket(client, key).status_code == 202


def test_version_conflict_and_patch_replay_preserve_audit(api, test_engine):
    client, user, _ = api
    created = create_ticket(client).json()
    path = f"/api/v1/tickets/{created['ticket_id']}"
    body = {"action_id": str(uuid4()), "expected_version": 1, "priority": "urgent", "assignee_id": str(user.id)}
    first = client.patch(path, json=body)
    assert first.status_code == 200 and first.json()["version"] == 2
    assert client.patch(path, json=body).json() == first.json()
    stale = client.patch(path, json={**body, "action_id": str(uuid4()), "priority": "low"})
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "VERSION_CONFLICT"
    assert client.get(path).json()["priority"] == "urgent"
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(AuditEvent).where(AuditEvent.ticket_id == UUID(created["ticket_id"]))) == 2
        run = db.get(Run, UUID(created["run_id"]))
        assert run.case_version == 2
        snapshot = db.scalar(select(CaseSnapshot).where(CaseSnapshot.run_id == run.id, CaseSnapshot.case_version == 2))
        assert snapshot.state_json["ticket_metadata"]["priority"] == "urgent"


def test_parallel_updates_have_one_winner(api):
    client, _, _ = api
    created = create_ticket(client).json()
    path, barrier = f"/api/v1/tickets/{created['ticket_id']}", Barrier(2)

    def change(priority):
        with TestClient(app) as worker:
            worker.cookies.update(client.cookies)
            worker.headers["X-CSRF-Token"] = client.headers["X-CSRF-Token"]
            barrier.wait(timeout=10)
            return worker.patch(path, json={"action_id": str(uuid4()), "expected_version": 1, "priority": priority}).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(change, ["low", "urgent"]))
    assert sorted(statuses) == [200, 409]
    assert client.get(path).json()["version"] == 2


def test_invalid_assignee_and_running_ticket_cannot_be_patched(api, test_engine, account_factory):
    client, _, _ = api
    knowledge_user, _ = account_factory(Role.KNOWLEDGE_ADMIN)
    created = create_ticket(client).json()
    path = f"/api/v1/tickets/{created['ticket_id']}"
    body = {"action_id": str(uuid4()), "expected_version": 1, "assignee_id": str(knowledge_user.id)}
    assert client.patch(path, json=body).status_code == 422
    with Session(test_engine) as db:
        db.execute(update(Ticket).where(Ticket.id == UUID(created["ticket_id"])).values(status="RUNNING"))
        db.execute(update(Run).where(Run.id == UUID(created["run_id"])).values(status="running"))
        db.commit()
    assert client.patch(path, json={"action_id": str(uuid4()), "expected_version": 1, "priority": "high"}).status_code == 409
    assert client.get(path).json()["version"] == 1


def test_list_cursor_filters_and_incremental_events(api):
    client, user, _ = api
    paths = []
    for _ in range(3):
        created = create_ticket(client).json()
        path = f"/api/v1/tickets/{created['ticket_id']}"
        paths.append(path)
        assert client.patch(path, json={"action_id": str(uuid4()), "expected_version": 1, "assignee_id": str(user.id)}).status_code == 200
    query = {"limit": 1, "assignee_id": str(user.id), "status": "QUEUED"}
    page = client.get("/api/v1/tickets", params=query).json()
    seen = [page["items"][0]["id"]]
    cursor = page["next_cursor"]
    create_ticket(client)
    while cursor:
        page = client.get("/api/v1/tickets", params={**query, "cursor": cursor}).json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 3
    assert client.get("/api/v1/tickets", params={"cursor": "bad"}).status_code == 422
    first = client.get(paths[0] + "/events", params={"limit": 1}).json()
    assert first["has_more"] is True
    second = client.get(paths[0] + "/events", params={"after_id": first["next_after_id"]}).json()
    assert len(second["items"]) == 1 and second["items"][0]["id"] > first["next_after_id"]


def test_database_constraints_block_second_active_run_and_cross_ticket_pointer(api, test_engine):
    client, _, _ = api
    one, two = create_ticket(client).json(), create_ticket(client).json()
    with Session(test_engine) as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.add(Run(ticket_id=UUID(one["ticket_id"]), thread_id=str(uuid4()), graph_version="test", case_version=1))
            db.flush()
        with pytest.raises(IntegrityError), db.begin_nested():
            task = db.get(ExecutionTask, UUID(one["task_id"]))
            db.add(ExecutionTask(run_id=task.run_id, kind=task.kind, action_id=task.action_id))
            db.flush()
        with pytest.raises(IntegrityError):
            db.execute(update(Ticket).where(Ticket.id == UUID(one["ticket_id"])).values(active_run_id=UUID(two["run_id"])))
            db.commit()
        db.rollback()


@pytest.mark.parametrize("change", [
    {"customer_email": "invalid"}, {"feedback_text": " "},
    {"occurred_at": "2026-11-18T10:00:00"}, {"status": "RESOLVED"},
    {"artifact_ids": [str(uuid4())]},
])
def test_invalid_or_not_yet_supported_inputs_are_rejected(api, change):
    client, _, _ = api
    response = create_ticket(client, **change)
    assert response.status_code == 422
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "input" not in response.json()["error"]["details"]


def test_missing_identifiers_unknown_records_and_forbidden_origin(api):
    client, _, _ = api
    assert client.post("/api/v1/tickets", json=PAYLOAD).status_code == 422
    assert client.get(f"/api/v1/tickets/{uuid4()}").status_code == 404
    assert client.get(f"/api/v1/runs/{uuid4()}").status_code == 404
    assert create_ticket(client, feedback_text="another").status_code == 202
    response = client.post("/api/v1/tickets", json=PAYLOAD, headers={"Origin": "https://untrusted.example", "Idempotency-Key": str(uuid4())})
    assert response.status_code == 403
