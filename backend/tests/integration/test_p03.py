from uuid import UUID, uuid4

import pytest

from app.workers.runtime import run_once


pytestmark = pytest.mark.integration


def post(client, path, **body):
    response = client.post(f"/api/v1/{path}", json={"action_id": str(uuid4()), **body})
    assert response.status_code in {200, 202}, response.text
    return response.json()


def test_closed_detail_preserves_latest_run_and_human_fact_sources(api):
    client, _, _ = api
    response = client.post("/api/v1/tickets", headers={"Idempotency-Key": str(uuid4())},
                           json={"customer_email": "p03@example.test", "feedback_text": "P03 事实与终态轨迹"})
    assert response.status_code == 202
    created = response.json()
    run_once(UUID(created["run_id"]))
    path = f"/api/v1/tickets/{created['ticket_id']}"
    detail = client.get(path).json()
    claimed = post(client, f"human-tasks/{detail['human_task_id']}/claim", expected_version=detail["version"])
    post(client, f"human-tasks/{detail['human_task_id']}/resume", expected_version=claimed["version"],
         facts_patch={"device_ref": "P03-DEVICE", "occurred_at": "2026-11-19T10:30:00+08:00"})
    run_once(UUID(created["run_id"]))
    ready = client.get(path).json()
    post(client, f"tickets/{created['ticket_id']}/close", expected_version=ready["version"],
         outcome="resolved", reason="模拟人工已核验结果")
    closed = client.get(path).json()
    assert closed["active_run_id"] is None
    assert closed["latest_run_id"] == created["run_id"]
    facts = {fact["field"]: fact for fact in closed["facts"]}
    assert facts["device_ref"]["source_type"] == "human"
    assert facts["device_ref"]["value_json"]["value"] == "P03-DEVICE"
    assert facts["customer_email"]["source_type"] == "user"
    assert client.get(f"/api/v1/runs/{closed['latest_run_id']}").json()["nodes"]


def test_detail_uses_latest_fact_after_reinvestigation(api):
    client, _, _ = api
    created = client.post("/api/v1/tickets", headers={"Idempotency-Key": str(uuid4())}, json={
        "customer_email": "p03@example.test", "feedback_text": "P03 当前事实", "device_ref": "OLD",
        "occurred_at": "2026-11-19T10:00:00+08:00",
    }).json()
    run_once(UUID(created["run_id"]))
    path = f"/api/v1/tickets/{created['ticket_id']}"
    original = client.get(path).json()
    post(client, f"tickets/{created['ticket_id']}/reinvestigate", expected_version=original["version"],
         reason="人工核对后更正设备", facts_patch={"device_ref": "NEW"})
    current = client.get(path).json()
    devices = [fact for fact in current["facts"] if fact["field"] == "device_ref"]
    assert len(devices) == 1
    assert devices[0]["value_json"]["value"] == "NEW"
    assert devices[0]["fact_version"] > 1
