from uuid import UUID, uuid4, uuid5

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.providers.client import ModelProfile
from app.repositories.models import NodeRun, Run, Ticket, ToolExecution
from app.services.tickets import digest
from app.workers.checkpoints import checkpoint_connection, try_run_lock
from app.workers.runtime import claim_task, eligible_tasks, run_once


pytestmark = pytest.mark.integration


def create(client, **extra):
    response = client.post("/api/v1/tickets", json={"customer_email": "demo@example.test", "feedback_text": "P04 模拟连接", **extra},
                           headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 202, response.text
    return response.json()


def detail(client, ticket_id):
    response = client.get(f"/api/v1/tickets/{ticket_id}")
    assert response.status_code == 200
    return response.json()


def test_worker_uses_registered_tools_and_audits_mock_model_usage(api, test_engine, monkeypatch):
    from app.providers import client as module
    original, inputs = module.mock_transport, []

    async def capture(request):
        inputs.append(request.model_dump(mode="json"))
        return await original(request)

    monkeypatch.setattr(module, "mock_transport", capture)
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    assert run_once(run_id)
    assert detail(client, created["ticket_id"])["status"] == "PENDING_CONFIRMATION"
    assert inputs and "demo@example.test" not in str(inputs)
    with Session(test_engine) as db:
        ticket = db.get(Ticket, UUID(created["ticket_id"]))
        tools = list(db.scalars(select(ToolExecution).where(ToolExecution.run_id == run_id)))
        assert {row.tool_name for row in tools} == {"search_knowledge", "get_feedbacks"}
        for row in tools:
            result = row.result_refs
            assert result["source"]["query"]["customer_ref"] == f"customer:{ticket.id.hex}"
            assert result["source"]["record_ids"] == result["data_refs"] == result["evidence_refs"]
            assert result["fetched_at"] and result["data_source"] == "mock"
            assert "demo@example.test" not in str(result)
        node = db.scalar(select(NodeRun).where(NodeRun.run_id == run_id, NodeRun.node_name == "generate_solution"))
        assert node.usage_json["model_calls"] == 1 and node.usage_json["simulated"]
        assert node.usage_json["cost"] is None
        assert db.get(Run, run_id).budget_json["model_calls"] == 1


def test_unconfigured_role_provider_pauses_instead_of_using_mock_fallback(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(get_settings(), "model_profiles", {"solution": ModelProfile(provider="real-unconfigured")})
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    assert run_once(UUID(created["run_id"]))
    value = detail(client, created["ticket_id"])
    assert value["status"] == "WAITING_HUMAN" and value["solution_json"] == {}
    task = client.get(f"/api/v1/human-tasks/{value['human_task_id']}").json()
    assert task["reason_code"] == "PROVIDER_NOT_CONFIGURED"


def test_invalid_model_json_becomes_visible_human_task(api, monkeypatch):
    async def corrupt(_):
        return '{"data_source":"real", "reply_draft":"pretend success"}'

    monkeypatch.setattr("app.providers.client.mock_transport", corrupt)
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    assert run_once(UUID(created["run_id"]))
    value = detail(client, created["ticket_id"])
    assert value["status"] == "WAITING_HUMAN" and value["solution_json"] == {}
    task = client.get(f"/api/v1/human-tasks/{value['human_task_id']}").json()
    assert task["reason_code"] == "INVALID_MODEL_OUTPUT"


def test_legacy_mock_v1_tool_cache_is_still_reusable(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with checkpoint_connection() as connection:
        assert try_run_lock(connection, run_id)
        ctx, state, _, _, _ = claim_task(connection, eligible_tasks(run_id)[0])
        args = {"device_ref": state["request"]["device_ref"], "occurred_at": state["request"]["occurred_at"]}
        legacy = {"status": "success", "data_source": "mock", "evidence_refs": ["mock:mock_knowledge:v1"], "error_code": None}
        action_id = uuid5(run_id, "0:mock_knowledge:2:mock_knowledge")
        with Session(test_engine) as db:
            db.add(ToolExecution(run_id=run_id, logical_action_id=action_id, tool_name="mock_knowledge",
                                 args_hash=digest(args), status="succeeded", result_refs=legacy))
            db.commit()
        assert ctx.tool("mock_knowledge", state, "mock_knowledge:2") == legacy
