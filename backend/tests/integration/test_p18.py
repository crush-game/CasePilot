from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import httpx
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.schemas import TicketCreate
from app.config import get_settings
from app.domain.enums import Role
from app.main import app
from app.manage import create_user
from app.repositories.models import (
    Experience, QualityAssessment, QualitySnapshot, SupportConversation, SupportTurn, Ticket,
    TicketEvent, WeeklyDelivery, WeeklyReport,
)
from app.services import quality, weekly_reports as reports
from app.services.calendar import BEIJING
from app.services.deliveries import deliver_once
from app.services.tickets import create_ticket
from test_p06 import isolated
from test_p11 import login
from test_p17 import FORMAL, batch, begin, closed_body, decision, detail, queue_reply, rows_for


pytestmark = pytest.mark.integration
WEEK = date(2026, 10, 12)
START = datetime(2026, 10, 12, tzinfo=BEIJING)
REPORTS = "/api/v1/reports/weekly"


@pytest.fixture
def report_api(isolated, monkeypatch):
    monkeypatch.delenv("AFTERSALES_WEEKLY_REPORT_WEBHOOK", raising=False)
    get_settings.cache_clear()
    with Session(isolated, expire_on_commit=False) as db:
        password = uuid4().hex
        actor = create_user(db, "weekly_" + uuid4().hex, password, Role.BUSINESS)
    with TestClient(app, raise_server_exceptions=False) as client:
        login(client, actor, password)
        yield client, isolated, actor


def report_request(client):
    response = client.post(REPORTS, json={"week_start": WEEK.isoformat()})
    assert response.status_code == 200, response.text
    return response.json()


def seed_conversation(db, actor, when, *, ticket_path=None, solved=False):
    ticket_id = None
    if ticket_path:
        ticket = create_ticket(db, actor, str(uuid4()), TicketCreate(customer_email="report@example.test",
            feedback_text="Wi-Fi 反复断开"), source="app_support", handoff=ticket_path == "human")
        ticket_id = UUID(ticket["ticket_id"])
        db.execute(update(Ticket).where(Ticket.id == ticket_id).values(created_at=when))
        db.execute(update(TicketEvent).where(TicketEvent.ticket_id == ticket_id).values(created_at=when))
    row = SupportConversation(owner_id=actor.id, ticket_id=ticket_id, flow_version="support-v2", created_at=when)
    db.add(row)
    db.flush()
    db.add(SupportTurn(conversation_id=row.id, request_action="message", request_text="连接异常",
                       reply_json={"kind": "answer", "text": "请检查连接"}, created_at=when))
    if solved:
        db.add(SupportTurn(conversation_id=row.id, request_action="solved", request_text="回答已解决问题",
                           reply_json={"kind": "feedback", "text": "已确认"}, created_at=when))
    db.commit()
    return row


def test_beijing_week_counts_confirmed_outcomes_and_revisions(report_api):
    client, engine, actor = report_api
    with Session(engine, expire_on_commit=False) as db:
        seed_conversation(db, actor, START, solved=True)
        first = seed_conversation(db, actor, START + timedelta(days=1), ticket_path="human")
        second = seed_conversation(db, actor, START + timedelta(days=2), ticket_path="human")
        seed_conversation(db, actor, START + timedelta(days=3), ticket_path="queued")
        seed_conversation(db, actor, START - timedelta(seconds=1), solved=True)
        seed_conversation(db, actor, START + timedelta(days=7), solved=True)
        for _ in range(2):
            db.add(TicketEvent(ticket_id=second.ticket_id, event_type="human.claimed", payload_json={},
                               created_at=START + timedelta(days=3)))
        db.add(TicketEvent(ticket_id=first.ticket_id, event_type="ticket.closed",
                           payload_json={"outcome": "resolved"}, created_at=START + timedelta(days=4)))
        snapshot = QualitySnapshot(ticket_id=first.ticket_id, conversation_id=first.id, case_version=4,
                                   rule_version="v0.1", data_json={"missing": []},
                                   created_at=START + timedelta(days=4))
        db.add(snapshot)
        db.flush()
        score = QualityAssessment(snapshot_id=snapshot.id, subject_id=actor.id, rule_version="v0.1",
            status="finalized", result_json={"stage": "ai", "findings": [{"rule_id": "business_incomplete"}]},
            created_at=START + timedelta(days=8))
        db.add(score)
        db.commit()
        assessment_id = score.id
    original = report_request(client)
    assert original["revision"] == 1
    metrics = original["metrics_json"]
    assert metrics["self_resolved"] == {"count": 1, "total": 4}
    assert metrics["handoff"] == {"count": 2, "total": 4}
    assert metrics["new_tickets"] == 3 and metrics["pending_human_at_cutoff"] == 1
    assert metrics["faults"]["wifi"] == 3
    assert metrics["quality"] == {"total": 1, "reviewed": 1, "screened": 1, "ai_checked": 1, "insufficient": 0}
    assert metrics["deductions"][0]["count"] == 1
    assert report_request(client)["id"] == original["id"]
    with Session(engine) as db:
        db.get(QualityAssessment, assessment_id).result_json = {"stage": "ai", "findings": []}
        db.commit()
    revision = report_request(client)
    assert revision["revision"] == 2 and revision["metrics_json"]["deductions"] == []
    assert client.get(f"{REPORTS}/{original['id']}").json()["metrics_json"]["deductions"] == metrics["deductions"]
    assert client.post(REPORTS, json={"week_start": "2026-10-13"}).status_code == 422


def test_scheduler_runs_after_monday_nine_and_only_enqueues_one_version(report_api, monkeypatch):
    _, engine, _ = report_api
    monkeypatch.setenv("AFTERSALES_WEEKLY_REPORT_ENABLED", "true")
    get_settings.cache_clear()
    when = START + timedelta(hours=9)
    assert not reports.schedule_once(when - timedelta(seconds=1))
    with Session(engine, expire_on_commit=False) as db:
        preview = reports.generate(db, now=when - timedelta(minutes=1))
        db.commit()
        assert db.scalar(select(WeeklyDelivery)) is None
    assert reports.schedule_once(when) and not reports.schedule_once(when + timedelta(hours=1))
    with Session(engine) as db:
        report = db.scalar(select(WeeklyReport))
        delivery = db.scalar(select(WeeklyDelivery))
        assert report.id == preview.id and report.week_start == WEEK - timedelta(days=7)
        assert delivery.report_id == report.id and delivery.mode == "mock"


def test_notification_retries_confirms_unknown_and_deduplicates(report_api):
    client, engine, _ = report_api
    report = report_request(client)
    endpoint = f"{REPORTS}/{report['id']}/delivery"
    first = client.post(endpoint)
    assert first.status_code == 202, first.text
    receipt = first.json()
    assert client.post(endpoint).json()["id"] == receipt["id"]
    delivery_id = UUID(receipt["id"])
    calls = []

    def attempt(mode, target, text):
        calls.append(text)
        assert mode == "mock" and "查看面板" in text and "example.test" not in text
        return ("retry", "RATE_LIMITED") if len(calls) == 1 else ("unknown", "TIMEOUT")

    assert reports.deliver_once(delivery_id, sender=attempt)
    assert not reports.deliver_once(delivery_id, sender=attempt)
    with Session(engine) as db:
        db.execute(update(WeeklyDelivery).where(WeeklyDelivery.id == delivery_id).values(available_at=func.clock_timestamp()))
        db.commit()
    assert reports.deliver_once(delivery_id, sender=attempt)
    assert not reports.deliver_once(delivery_id, sender=attempt)
    state = client.get(f"{REPORTS}/{report['id']}").json()["deliveries"][0]
    assert state["status"] == "unknown" and state["attempts"] == 2 and len(calls) == 2


def test_worker_crash_and_parallel_claim_do_not_repeat_delivery(report_api):
    client, engine, _ = report_api
    report = report_request(client)
    delivery_id = UUID(client.post(f"{REPORTS}/{report['id']}/delivery").json()["id"])
    entered, finished = Event(), Event()

    def fake_sender(*args):
        entered.set()
        assert finished.wait(8)
        raise RuntimeError("在记录回执前中断")

    with ThreadPoolExecutor(max_workers=1) as pool:
        active = pool.submit(reports.deliver_once, delivery_id, sender=fake_sender)
        try:
            assert entered.wait(8)
            assert not reports.deliver_once(delivery_id)
        finally:
            finished.set()
        with pytest.raises(RuntimeError, match="中断"):
            active.result(timeout=8)
    with Session(engine) as db:
        row = db.get(WeeklyDelivery, delivery_id)
        assert row.status == "sending" and row.attempts == 1
        row.started_at -= timedelta(seconds=31)
        db.commit()
    assert reports.deliver_once(delivery_id)
    assert not reports.deliver_once(delivery_id)
    with Session(engine) as db:
        row = db.get(WeeklyDelivery, delivery_id)
        assert row.status == "unknown" and row.receipt == "WORKER_RESPONSE_LOST" and row.attempts == 1


def test_remote_response_contract_without_external_call(report_api, monkeypatch):
    monkeypatch.setenv("AFTERSALES_WEEKLY_REPORT_WEBHOOK",
                       "https://open.feishu.cn/open-apis/bot/v2/hook/TEST_WEBHOOK_NO_REAL_CALL")
    get_settings.cache_clear()
    monkeypatch.setattr(reports.httpx, "post", lambda *_, **__: httpx.Response(200, json={"code": 0}))
    assert reports.send_notification("feishu", "after-sales", "汇总") == ("sent", "FEISHU_ACCEPTED")
    monkeypatch.setattr(reports.httpx, "post", lambda *_, **__: httpx.Response(200, json={"code": 11232}))
    assert reports.send_notification("feishu", "after-sales", "汇总") == ("retry", "RATE_LIMITED")
    monkeypatch.setattr(reports.httpx, "post", lambda *_, **__: httpx.Response(200, json={"unexpected": 0}))
    assert reports.send_notification("feishu", "after-sales", "汇总")[0] == "unknown"


def test_quality_gap_preserves_review_evidence_and_requires_knowledge_admin(api, account_factory, test_engine):
    client, _, _ = api
    ticket, version, _, _, _ = begin(api, account_factory, test_engine)
    assert deliver_once(queue_reply(client, ticket, version, FORMAL))
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    _, (entry,) = rows_for(test_engine, ticket)
    assert quality.process_one(assessment_id=entry.id)
    batch(client, ticket)
    assert quality.process_one(assessment_id=entry.id)
    reviewer, reviewer_password = account_factory()
    login(client, reviewer, reviewer_password)
    path = f"/api/v1/quality/assessments/{entry.id}/knowledge-gap"
    body = {"rule_id": "business_incomplete", "statement": "补充客服回复保修问题的说明。"}
    assert client.post(path, json=body).status_code == 409
    assert decision(client, detail(client, entry.id), "confirm").status_code == 200
    item = client.post(path, json=body)
    assert item.status_code == 201, item.text
    gap = item.json()
    assert gap["status"] == "pending" and gap["evidence_json"]["ticket_id"] == str(ticket)
    assert gap["evidence_json"]["refs"] and client.post(path, json=body).json()["id"] == gap["id"]
    resolve = f"/api/v1/knowledge-gaps/{gap['id']}/decision"
    result = {"decision": "confirmed", "reason": "已核对当前产品 FAQ。"}
    assert client.post(resolve, json=result).status_code == 403
    admin, password = account_factory(Role.KNOWLEDGE_ADMIN)
    login(client, admin, password)
    assert client.post(resolve, json=result).json()["status"] == "confirmed"
    with Session(test_engine) as db:
        assert db.scalar(select(Experience).where(Experience.source_ticket_id == ticket)) is None
