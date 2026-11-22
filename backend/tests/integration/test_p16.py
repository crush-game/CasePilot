import json
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import Role
from app.faults.source import FIXTURE_ROOT
from app.providers.ledger import create_budget
from app.providers.remote import ProviderSession
from app.repositories.models import ExecutionTask, HumanTask, LogArtifact, Run, SupportConversation, Ticket, TicketEvent, ToolExecution
from app.services.deliveries import deliver_once
from app.services.workflow_common import latest_snapshot
from test_p08 import advance, configuration, response
from test_p11 import login, turn


pytestmark = pytest.mark.integration
WIFI = "Wi-Fi 配对后复现断连"
DEVICE = {"device_ref": "P08-A", "platform": "android", "app_version": "2.0",
          "product_ref": "PILOT-01", "firmware_version": "1.0"}
REPAIR = {**DEVICE, "occurred_at": "2026-11-20T10:00:00+08:00"}


def setup(monkeypatch, tmp_path, user, email="p08-cross@example.test", tool_error=None):
    model = configuration()
    config = tmp_path / "provider.json"
    config.write_text(model.model_dump_json(), encoding="utf-8")
    data = json.loads((FIXTURE_ROOT / "p08-demo.json").read_text(encoding="utf-8"))
    if tool_error:
        data["tool_errors"]["download_log"] = tool_error
    (tmp_path / "p16-contract.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr("app.faults.source.FIXTURE_ROOT", tmp_path)
    monkeypatch.setenv("AFTERSALES_PROVIDER_CONFIG_PATH", str(config))
    monkeypatch.setenv("AFTERSALES_ENTERPRISE_MOCK_FIXTURE", "p16-contract")
    monkeypatch.setenv("AFTERSALES_SUPPORT_DEMO_DEVICES", json.dumps({
        str(user.id): [{**DEVICE, "customer_email": email}],
    }))
    get_settings.cache_clear()
    return model


def run_id_for(engine, offered):
    with Session(engine) as db:
        row = db.get(SupportConversation, UUID(offered["id"]))
        ticket = db.get(Ticket, row.ticket_id)
        return ticket.id, ticket.active_run_id


def run_contract(engine, run_id, model):
    client = ProviderSession(engine, create_budget(engine, scope="p16-contract", max_calls=20),
                             model, SecretStr("CONTRACT_TEST_KEY"),
                             transport=httpx.MockTransport(lambda request: response(request, "wifi")))
    assert advance(run_id, client)


@pytest.mark.parametrize("email,tool_error,stop", [
    ("p08-cross@example.test", None, None),
    ("p08-wifi-none@example.test", None, "TELEMETRY_ONLY"),
    ("p08-cross@example.test", "TIMEOUT", "TIMEOUT"),
    ("p08-multi@example.test", None, "FEEDBACK_SELECTION_REQUIRED"),
])
def test_consumer_submission_runs_authorized_fault_graph_and_preserves_outcome(
    api, account_factory, monkeypatch, test_engine, tmp_path, email, tool_error, stop,
):
    client, operator, operator_password = api
    customer, password = account_factory(Role.CONSUMER)
    model = setup(monkeypatch, tmp_path, customer, email, tool_error)
    login(client, customer, password)
    first = turn(client, flow_version="support-v2", text=WIFI)
    body = {"action_id": str(uuid4()), "action": "submit_fault", "conversation_id": first["id"], **REPAIR}
    submitted = client.post("/api/v1/support/turns", json=body)
    assert submitted.status_code == 201, submitted.text
    accepted = submitted.json()
    assert accepted["ticket_status"] == "QUEUED" and accepted["turn"]["reply_json"]["kind"] == "investigation_queued"
    assert "已转人工" not in accepted["turn"]["reply_json"]["text"]
    assert client.post("/api/v1/support/turns", json=body).json() == accepted
    assert turn(client, action="submit_fault", conversation_id=first["id"], **REPAIR)["ticket_no"] == accepted["ticket_no"]
    ticket_id, run_id = run_id_for(test_engine, first)
    with Session(test_engine) as db:
        assert db.get(Ticket, ticket_id).customer_email == email
        assert db.get(Run, run_id).graph_version == "supervisor-v2"
        assert latest_snapshot(db, run_id)["agent_config"]["enterprise"]["fixture_key"] == "p16-contract"
        assert db.scalar(select(func.count()).select_from(ExecutionTask).where(ExecutionTask.run_id == run_id)) == 1
        assert db.scalar(select(HumanTask).where(HumanTask.ticket_id == ticket_id)) is None
    run_contract(test_engine, run_id, model)
    with Session(test_engine) as db:
        ticket = db.get(Ticket, ticket_id)
        assert db.get(Run, run_id).stop_reason == stop
        tools = list(db.scalars(select(ToolExecution.tool_name).where(ToolExecution.run_id == run_id)))
        assert ("get_wifi_telemetry" in tools) == (stop == "TELEMETRY_ONLY")
        assert ticket.status == ("WAITING_HUMAN" if stop else "PENDING_CONFIRMATION")
        version = ticket.version
        if stop:
            return
        assert db.scalar(select(LogArtifact).where(LogArtifact.run_id == run_id))
        assert not ticket.solution_json["reviewed"]
    login(client, operator, operator_password)
    assert client.get(f"/api/v1/tickets/{ticket_id}/support-conversation").json()["turns"][0]["request_text"] == WIFI
    review = client.post(f"/api/v1/tickets/{ticket_id}/review", json={
        "action_id": str(uuid4()), "expected_version": version, "decision": "approve",
    })
    assert review.status_code == 200, review.text
    note = "请重新配对，并测试无线连接。"
    reply = client.post(f"/api/v1/tickets/{ticket_id}/support-replies", json={
        "action_id": str(uuid4()), "expected_version": review.json()["version"], "text": note,
    })
    assert reply.status_code == 202, reply.text
    login(client, customer, password)
    path = f"/api/v1/support/conversations/{first['id']}"
    assert note not in str(client.get(path).json())
    assert deliver_once(UUID(reply.json()["id"]))
    assert client.get(path).json()["turns"][-1]["reply_json"]["text"] == note


@pytest.mark.parametrize("action,question,changes", [
    ("submit_fault", WIFI, {"platform": None}),
    ("submit_fault", WIFI, {"occurred_at": None}),
    ("submit_fault", WIFI, {"device_ref": "OTHER-DEVICE"}),
    ("submit_fault", "OTA 升级失败，显示 Wi-Fi 断开", {}),
    ("handoff", WIFI, {}),
])
def test_incomplete_unowned_out_of_scope_and_explicit_handoff_are_manual(
    api, account_factory, monkeypatch, test_engine, tmp_path, action, question, changes,
):
    client, _, _ = api
    customer, password = account_factory(Role.CONSUMER)
    setup(monkeypatch, tmp_path, customer)
    login(client, customer, password)
    first = turn(client, flow_version="support-v2", text=question)
    result = turn(client, action=action, conversation_id=first["id"], **{**REPAIR, **changes})
    assert result["ticket_status"] == "WAITING_HUMAN"
    assert result["turn"]["reply_json"]["kind"] == "handoff"
    ticket_id, run_id = run_id_for(test_engine, first)
    with Session(test_engine) as db:
        email = (f"consumer-{customer.id.hex}@example.test" if action == "handoff" or "device_ref" in changes
                 else "p08-cross@example.test")
        assert db.get(Ticket, ticket_id).customer_email == email
        assert db.scalar(select(HumanTask).where(HumanTask.ticket_id == ticket_id)) is not None
        assert db.scalar(select(ExecutionTask).where(ExecutionTask.run_id == run_id)) is None
        assert db.scalar(select(ToolExecution).where(ToolExecution.run_id == run_id)) is None


def test_customer_supplement_and_corrected_facts_keep_original_investigation(
    api, account_factory, monkeypatch, test_engine, tmp_path,
):
    client, operator, operator_password = api
    customer, password = account_factory(Role.CONSUMER)
    model = setup(monkeypatch, tmp_path, customer)
    login(client, customer, password)
    first = turn(client, flow_version="support-v2", text=WIFI)
    accepted = turn(client, action="submit_fault", conversation_id=first["id"], **REPAIR)
    ticket_id, run_id = run_id_for(test_engine, first)
    supplement = "我确认刚才填错了 App 版本，应该是 2.1。"
    assert turn(client, conversation_id=first["id"], text=supplement)["ticket_no"] == accepted["ticket_no"]
    run_contract(test_engine, run_id, model)
    with Session(test_engine) as db:
        version = db.get(Ticket, ticket_id).version
        assert latest_snapshot(db, run_id)["request"]["app_version"] == "2.0"
        assert db.scalar(select(TicketEvent).where(TicketEvent.ticket_id == ticket_id,
            TicketEvent.event_type == "support.message_received")).payload_json["message"] == supplement
    login(client, operator, operator_password)
    corrected = client.post(f"/api/v1/tickets/{ticket_id}/reinvestigate", json={
        "action_id": str(uuid4()), "expected_version": version, "reason": "用户补充了正确版本",
        "facts_patch": {"app_version": "2.1"},
    })
    assert corrected.status_code == 202, corrected.text
    with Session(test_engine) as db:
        new_run = db.get(Ticket, ticket_id).active_run_id
        assert new_run != run_id and latest_snapshot(db, new_run)["request"]["app_version"] == "2.1"
        assert db.get(Run, new_run).graph_version == "supervisor-v2"
        assert latest_snapshot(db, run_id)["solution"]["evidence_refs"]
        assert db.scalar(select(LogArtifact).where(LogArtifact.run_id == run_id))
