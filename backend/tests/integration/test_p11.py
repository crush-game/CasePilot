from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.support_schemas import SupportMessage
from app.domain.enums import Role
from app.repositories.models import ExecutionTask, HumanTask, SupportConversation, SupportTurn, Ticket, TicketEvent
from app.services import support


pytestmark = pytest.mark.integration


def login(client, user, password):
    response = client.post("/api/v1/auth/login", json={"login": user.login, "password": password})
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]


def turn(client, **fields):
    response = client.post("/api/v1/support/turns", json={"action_id": str(uuid4()), **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_consumer_faq_clarification_and_owned_history(api, account_factory):
    client, _, _ = api
    path = "/api/v1/support/conversations"
    assert client.get(path).status_code == 403
    user, password = account_factory(Role.CONSUMER)
    login(client, user, password)
    assert client.get("/api/v1/tickets").status_code == 403

    direct = turn(client, text="怎么查看 App 版本？")
    assert direct["turn"]["reply_json"]["kind"] == "answer" and direct["ticket_no"] is None
    assert direct["turn"]["reply_json"]["evidence_ref"] == "faq:demo-version:v1"

    first = turn(client, text="怎么连接设备？")
    assert first["turn"]["reply_json"]["kind"] == "clarify" and first["ticket_no"] is None
    answered = turn(client, action="clarify", conversation_id=first["id"], product_ref="DEMO-01", firmware_version="1.0")
    assert answered["turn"]["reply_json"]["kind"] == "answer" and answered["ticket_no"] is None
    assert turn(client, action="solved", conversation_id=first["id"])["turn"]["reply_json"]["kind"] == "feedback"
    assert len(client.get(path + "/" + first["id"]).json()["turns"]) == 3

    other, secret = account_factory(Role.CONSUMER)
    login(client, other, secret)
    assert client.get(path).json() == []
    assert client.get(path + "/" + first["id"]).status_code == 404
    assert client.post("/api/v1/support/turns", json={"action_id": str(uuid4()), "conversation_id": first["id"],
        "action": "handoff"}).status_code == 404


def test_handoff_replay_links_one_ticket_and_one_task_and_records_supplement(api, account_factory, test_engine):
    client, _, _ = api
    user, password = account_factory(Role.CONSUMER)
    login(client, user, password)
    path = "/api/v1/support/turns"
    body = {"action_id": str(uuid4()), "action": "handoff", "text": "设备异常 p11-private@example.test"}
    first = client.post(path, json=body)
    assert first.status_code == 201
    value = first.json()
    assert client.post(path, json=body).json() == value
    assert client.post(path, json={**body, "text": "改写后的问题"}).status_code == 409
    assert value["turn"]["reply_json"]["kind"] == "handoff" and value["ticket_status"] == "WAITING_HUMAN"
    assert value["ticket_no"].startswith("CP-") and "p11-private" not in str(value)
    assert turn(client, conversation_id=value["id"], text="重启后仍出现")["turn"]["reply_json"]["kind"] == "received"
    with Session(test_engine) as db:
        conversation = db.get(SupportConversation, UUID(value["id"]))
        ticket = db.get(Ticket, conversation.ticket_id)
        assert ticket.created_by == user.id and ticket.source == "app_support"
        assert ticket.customer_email == f"consumer-{user.id.hex}@example.test"
        assert "p11-private" not in ticket.feedback_text
        assert db.scalar(select(func.count()).select_from(HumanTask).where(HumanTask.ticket_id == ticket.id)) == 1
        assert db.scalar(select(ExecutionTask).where(ExecutionTask.run_id == ticket.active_run_id)) is None
        assert db.scalar(select(TicketEvent).where(TicketEvent.ticket_id == ticket.id,
            TicketEvent.event_type == "support.message_received")).payload_json["message"] == "重启后仍出现"
        assert db.scalar(select(func.count()).select_from(SupportTurn).where(SupportTurn.conversation_id == conversation.id)) == 2


def test_concurrent_handoff_reuses_active_ticket(api, account_factory, test_engine):
    client, _, _ = api
    user, password = account_factory(Role.CONSUMER)
    login(client, user, password)
    first = turn(client, text="怎么查看 App 版本？")
    def act(_):
        with Session(test_engine) as db:
            return support.submit(db, user, SupportMessage(action_id=uuid4(), conversation_id=UUID(first["id"]), action="handoff"))
    with ThreadPoolExecutor(max_workers=2) as pool:
        both = list(pool.map(act, [0, 1]))
    assert len({row["ticket_no"] for row in both}) == 1
    assert {row["turn"]["reply_json"]["kind"] for row in both} == {"handoff", "received"}


def test_handoff_rollback_never_returns_receipt(api, account_factory, test_engine, monkeypatch):
    client, _, _ = api
    user, password = account_factory(Role.CONSUMER)
    login(client, user, password)
    original = support.SupportAccepted
    def fail(**kwargs):
        raise RuntimeError("fixture failure before commit")
    monkeypatch.setattr(support, "SupportAccepted", fail)
    body = {"action_id": str(uuid4()), "text": "未覆盖的模拟异常"}
    assert client.post("/api/v1/support/turns", json=body).status_code == 500
    with Session(test_engine) as db:
        assert db.scalar(select(Ticket).where(Ticket.created_by == user.id)) is None
        assert db.scalar(select(SupportConversation).where(SupportConversation.owner_id == user.id)) is None
    monkeypatch.setattr(support, "SupportAccepted", original)
    assert client.post("/api/v1/support/turns", json=body).status_code == 201


def test_wrong_firmware_and_unknown_query_use_manual_fallback(api, account_factory):
    client, _, _ = api
    user, password = account_factory(Role.CONSUMER)
    login(client, user, password)
    first = turn(client, text="怎么连接设备？", product_ref="DEMO-01", firmware_version="9.9")
    assert first["turn"]["reply_json"]["kind"] == "handoff"
    assert first["turn"]["reply_json"]["evidence_ref"] is None
    second = turn(client, text="未定义的政策问答")
    assert second["ticket_status"] == "WAITING_HUMAN"
    assert first["ticket_no"] != second["ticket_no"]
