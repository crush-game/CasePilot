from datetime import datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.repositories.models import ChannelEvent, HumanTask, SupportDelivery, Ticket
from app.services.calendar import ServiceCalendar
from app.services.deliveries import deliver_once
from test_p11 import login, turn


def event_for(sender_id, **changes):
    return {"event_id": str(uuid4()), "sender_id": str(sender_id), "conversation_ref": "demo-session",
            "issue_ref": "first", "reply_target": "demo-inbox", "sequence": 1,
            "occurred_at": "2026-11-21T10:00:00+08:00", "text": "模拟未覆盖故障", **changes}


def make_due(engine, delivery_id):
    with Session(engine) as db:
        db.execute(update(SupportDelivery).where(SupportDelivery.id == delivery_id).values(available_at=func.clock_timestamp()))
        db.commit()


@pytest.mark.integration
def test_mock_event_dedup_out_of_order_edits_and_issue_isolation(api, account_factory, test_engine):
    client, _, _ = api
    consumer, _ = account_factory(Role.CONSUMER)
    path = "/api/v1/channels/mock/events"
    body = event_for(consumer.id, sequence=3)
    created = client.post(path, json=body)
    assert created.status_code == 202, created.text
    first = created.json()
    assert first["ticket_no"].startswith("CP-")
    assert client.post(path, json=body).json() == first
    assert client.post(path, json={**body, "text": "altered"}).status_code == 409
    older = client.post(path, json=event_for(consumer.id, sequence=2)).json()
    assert older["disposition"] == "historical" and older["delivery_id"] is None
    edit = client.post(path, json=event_for(consumer.id, sequence=4, kind="edit")).json()
    assert edit["disposition"] == "edited" and edit["delivery_id"] is None
    newer = client.post(path, json=event_for(consumer.id, sequence=5, text="补充信息")).json()
    assert newer["ticket_no"] == first["ticket_no"] and newer["delivery_id"] != first["delivery_id"]
    other = client.post(path, json=event_for(consumer.id, issue_ref="second")).json()
    assert other["ticket_no"] != first["ticket_no"]
    with Session(test_engine) as db:
        assert db.scalar(select(ChannelEvent).where(ChannelEvent.id == UUID(older["event_id"]))).event_json["sequence"] == 2
        assert db.scalar(select(Ticket).where(Ticket.ticket_no == first["ticket_no"])).feedback_text == body["text"]


@pytest.mark.integration
@pytest.mark.parametrize("failures,final", [(1, "delivered"), (3, "failed")])
def test_delivery_retries_with_durable_status_without_rolling_back_ticket(api, account_factory, test_engine, failures, final):
    client, _, _ = api
    consumer, _ = account_factory(Role.CONSUMER)
    result = client.post("/api/v1/channels/mock/events", json=event_for(consumer.id, simulated_failures=failures))
    assert result.status_code == 202
    accepted = result.json()
    delivery_id = UUID(accepted["delivery_id"])
    path = f"/api/v1/channels/deliveries/{delivery_id}"
    queued = client.get(path).json()
    assert queued["status"] == "queued" and queued["attempts"] == 0 and queued["provider_ref"] is None
    assert deliver_once(delivery_id)
    assert not deliver_once(delivery_id)
    interim = client.get(path).json()
    assert interim["status"] == "queued" and interim["last_error"] == "MOCK_DELIVERY_FAILED"
    for _ in range(1 if final == "delivered" else 2):
        make_due(test_engine, delivery_id)
        assert deliver_once(delivery_id)
    sent = client.get(path).json()
    assert sent["status"] == final and (sent["provider_ref"] is not None) == (final == "delivered")
    assert not deliver_once(delivery_id)
    with Session(test_engine) as db:
        ticket = db.scalar(select(Ticket).where(Ticket.ticket_no == accepted["ticket_no"]))
        assert ticket.status == "WAITING_HUMAN"
        assert db.scalar(select(HumanTask).where(HumanTask.ticket_id == ticket.id)).status == "unclaimed"


@pytest.mark.integration
def test_app_human_reply_becomes_visible_only_after_delivery(api, account_factory, test_engine):
    client, operator, password = api
    customer, secret = account_factory(Role.CONSUMER)
    login(client, customer, secret)
    accepted = turn(client, action="handoff", text="请人工处理")
    conversation_path = f"/api/v1/support/conversations/{accepted['id']}"
    login(client, operator, password)
    with Session(test_engine) as db:
        ticket = db.scalar(select(Ticket).where(Ticket.ticket_no == accepted["ticket_no"]))
        task = db.scalar(select(HumanTask).where(HumanTask.ticket_id == ticket.id))
        ticket_id, task_id = ticket.id, task.id
    path = f"/api/v1/tickets/{ticket_id}/support-replies"
    payload = {"action_id": str(uuid4()), "expected_version": 1, "text": "请补充设备故障时间"}
    assert client.post(path, json=payload).status_code == 403
    claimed = client.post(f"/api/v1/human-tasks/{task_id}/claim",
                          json={"action_id": str(uuid4()), "expected_version": 1})
    assert claimed.status_code == 200
    payload["expected_version"] = claimed.json()["version"]
    response = client.post(path, json=payload)
    assert response.status_code == 202
    delivery = response.json()
    assert delivery["status"] == "queued" and client.post(path, json=payload).json() == delivery
    login(client, customer, secret)
    assert not any(row["reply_json"]["kind"] == "agent_reply" for row in client.get(conversation_path).json()["turns"])
    assert deliver_once(UUID(delivery["id"])) and not deliver_once(UUID(delivery["id"]))
    turns = client.get(conversation_path).json()["turns"]
    assert len(turns) == 2 and turns[-1]["reply_json"]["text"] == payload["text"]
    assert client.get(f"/api/v1/channels/deliveries/{delivery['id']}").status_code == 403


def test_calendar_skips_closed_dates_without_promising_resolution():
    calendar = ServiceCalendar(weekdays=[0, 1, 2, 3, 4], opens="09:00", closes="18:00",
                               closed_dates=["2026-11-23"])
    assert "2026-11-24 09:00" in calendar.receipt(datetime.fromisoformat("2026-11-21T10:00:00+08:00"))
    assert "当前处于" in calendar.receipt(datetime.fromisoformat("2026-11-24T09:00:00+08:00"))
    assert "2026-11-25 09:00" in calendar.receipt(datetime.fromisoformat("2026-11-24T18:00:00+08:00"))
