from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.support_schemas import SupportMessage
from app.domain.enums import Role
from app.repositories.models import HumanTask, SupportConversation, SupportDelivery, SupportTurn, Ticket
from app.services import support
from app.services.deliveries import deliver_once
from test_p11 import login, turn


pytestmark = pytest.mark.integration
TURNS = "/api/v1/support/turns"


def test_new_flow_offers_confirmation_and_preserves_faq_and_scope(api, account_factory, test_engine):
    client, _, _ = api
    customer, password = account_factory(Role.CONSUMER)
    login(client, customer, password)
    faq = turn(client, flow_version="support-v2", text="怎么查看 App 版本？")
    assert faq["turn"]["reply_json"]["evidence_ref"] == "faq:demo-version:v1"
    assert turn(client, action="solved", conversation_id=faq["id"])["ticket_no"] is None

    first = turn(client, flow_version="support-v2", text="怎么连接设备？")
    assert first["turn"]["reply_json"]["kind"] == "clarify"
    offer = turn(client, action="clarify", conversation_id=first["id"], product_ref="DEMO-01", firmware_version="9.9")
    assert offer["ticket_no"] is None and offer["flow_version"] == "support-v2"
    assert offer["turn"]["reply_json"]["offer"] == {
        "question": "怎么连接设备？", "product_ref": "DEMO-01", "firmware_version": "9.9", "missing_fields": [],
    }
    conflict = client.post(TURNS, json={
        "action_id": str(uuid4()), "conversation_id": first["id"], "flow_version": "support-v1", "action": "handoff",
    })
    assert conflict.status_code == 409
    with Session(test_engine) as db:
        assert db.scalar(select(Ticket).where(Ticket.created_by == customer.id)) is None
    confirmed = turn(client, action="handoff", conversation_id=first["id"], firmware_version="9.8")
    with Session(test_engine) as db:
        row = db.get(SupportConversation, UUID(first["id"]))
        ticket = db.get(Ticket, row.ticket_id)
        assert confirmed["ticket_no"] == ticket.ticket_no
        assert ticket.feedback_text == "怎么连接设备？"
        assert ticket.status == "WAITING_HUMAN"
    assert confirmed["turn"]["reply_json"]["kind"] == "handoff"


def test_confirmation_concurrency_and_conflicting_reuse(api, account_factory, test_engine):
    client, _, _ = api
    customer, password = account_factory(Role.CONSUMER)
    login(client, customer, password)
    offered = turn(client, flow_version="support-v2", text="升级后 Wi-Fi 反复断开")
    reply = offered["turn"]["reply_json"]
    assert reply["kind"] == "handoff_offer" and offered["ticket_no"] is None
    assert reply["offer"]["missing_fields"] == ["product_ref", "firmware_version"]
    conversation_id = UUID(offered["id"])
    keys = [uuid4(), uuid4()]

    def confirm(key):
        body = SupportMessage(action_id=key, conversation_id=conversation_id, action="handoff")
        with Session(test_engine) as db:
            return support.submit(db, customer, body)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = list(pool.map(confirm, keys))
    assert first["ticket_no"] == second["ticket_no"]
    assert confirm(keys[0]) == first
    conflict = client.post(TURNS, json={
        "action_id": str(keys[0]), "conversation_id": offered["id"], "action": "handoff", "text": "更改的内容",
    })
    assert conflict.status_code == 409
    with Session(test_engine) as db:
        ticket_id = db.get(SupportConversation, conversation_id).ticket_id
        assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.created_by == customer.id)) == 1
        assert db.scalar(select(func.count()).select_from(HumanTask).where(HumanTask.ticket_id == ticket_id)) == 1


def test_confirmation_rollback_and_response_replay(api, account_factory, test_engine, monkeypatch):
    client, _, _ = api
    customer, password = account_factory(Role.CONSUMER)
    login(client, customer, password)
    offered = turn(client, flow_version="support-v2", text="模拟断连")
    body = {"action_id": str(uuid4()), "conversation_id": offered["id"], "action": "handoff"}
    with monkeypatch.context() as patch:
        def fail_before_commit(**data):
            raise RuntimeError("模拟回执生成失败")

        patch.setattr(support, "SupportAccepted", fail_before_commit)
        assert client.post(TURNS, json=body).status_code == 500
    with Session(test_engine) as db:
        assert db.get(SupportConversation, UUID(offered["id"])).ticket_id is None
        assert db.scalar(select(Ticket).where(Ticket.created_by == customer.id)) is None
        assert db.scalar(select(func.count()).select_from(SupportTurn).where(
            SupportTurn.conversation_id == UUID(offered["id"]))) == 1
    first = client.post(TURNS, json=body)
    assert first.status_code == 201
    assert client.post(TURNS, json=body).json() == first.json()


def test_formal_reply_links_actual_employee_and_original_conversation(api, account_factory, test_engine):
    client, operator, operator_password = api
    customer, password = account_factory(Role.CONSUMER)
    login(client, customer, password)
    offered = turn(client, flow_version="support-v2", text="升级后反复断连")
    accepted = turn(client, conversation_id=offered["id"], action="handoff")
    conversation_id = UUID(accepted["id"])
    conversation_path = f"/api/v1/support/conversations/{conversation_id}"
    other, other_password = account_factory(Role.CONSUMER)
    login(client, other, other_password)
    assert client.get(conversation_path).status_code == 404
    assert client.post(TURNS, json={
        "action_id": str(uuid4()), "conversation_id": accepted["id"], "text": "越权消息",
    }).status_code == 404
    login(client, customer, password)
    supplemented = turn(client, conversation_id=accepted["id"], text="重新配对后仍能复现")
    assert supplemented["ticket_no"] == accepted["ticket_no"]
    with Session(test_engine) as db:
        ticket_id = db.get(SupportConversation, conversation_id).ticket_id
        task_id = db.scalar(select(HumanTask.id).where(HumanTask.ticket_id == ticket_id))
    login(client, operator, operator_password)
    reply_path = f"/api/v1/tickets/{ticket_id}/support-replies"
    request = {"action_id": str(uuid4()), "expected_version": 1, "text": "请提供复现发生时间。"}
    assert client.post(reply_path, json=request).status_code == 403
    claim = client.post(f"/api/v1/human-tasks/{task_id}/claim", json={
        "action_id": str(uuid4()), "expected_version": 1,
    })
    assert claim.status_code == 200
    sent = client.post(reply_path, json={**request, "expected_version": claim.json()["version"]})
    assert sent.status_code == 202
    delivery_id = UUID(sent.json()["id"])
    login(client, customer, password)
    assert all(row["reply_json"]["kind"] != "agent_reply" for row in client.get(conversation_path).json()["turns"])
    assert deliver_once(delivery_id) and not deliver_once(delivery_id)
    reply = client.get(conversation_path).json()["turns"][-1]
    assert reply["reply_json"]["text"] == request["text"]
    assert str(operator.id) not in str(reply)
    with Session(test_engine) as db:
        delivery = db.get(SupportDelivery, delivery_id)
        assert delivery.reply_author_id == operator.id
        assert delivery.status == "delivered" and delivery.provider_ref == f"app:{reply['id']}"
        assert db.get(SupportTurn, supplemented["turn"]["id"]).request_action == "message"
