from contextlib import contextmanager
from datetime import timedelta
import json
import os
import queue
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.repositories.models import ExecutionTask, HumanAction, HumanTask, NodeRun, Run, Ticket, ToolExecution
from app.repositories.database import get_engine
from app.workers.runtime import run_once
from app.main import app
from app.config import get_settings
from app.workers.runtime import claim_task, eligible_tasks
from app.workers.checkpoints import checkpoint_connection, try_run_lock
from app.workers.context import Heartbeat, LeaseLost
from app.workers.projection import project_result
from app.agents.graphs.mock import build_graph
from langgraph.checkpoint.postgres import PostgresSaver


pytestmark = pytest.mark.integration


def create(client, **extra):
    response = client.post("/api/v1/tickets", json={"customer_email": "demo@example.test", "feedback_text": "设备反复断连", **extra},
                           headers={"Idempotency-Key": str(uuid4())})
    assert response.status_code == 202
    return response.json()


def detail(client, ticket_id):
    response = client.get(f"/api/v1/tickets/{ticket_id}")
    assert response.status_code == 200
    return response.json()


def action(client, path, version, **extra):
    return client.post(f"/api/v1/{path}", json={"action_id": str(uuid4()), "expected_version": version, **extra})


def claim(client, ticket):
    response = action(client, f"human-tasks/{ticket['human_task_id']}/claim", ticket["version"])
    assert response.status_code == 200, response.text
    return response.json()


def test_mock_create_pause_claim_resume_solution_review_contact_close(api, test_engine):
    client, _, _ = api
    created = create(client)
    run_id = UUID(created["run_id"])
    assert run_once(run_id)
    paused = detail(client, created["ticket_id"])
    assert paused["status"] == "WAITING_HUMAN" and paused["human_task_id"]
    task = client.get(f"/api/v1/human-tasks/{paused['human_task_id']}").json()
    assert task["payload_json"]["missing_fields"] == ["device_ref", "occurred_at"]
    claimed = claim(client, paused)
    body = {"action_id": str(uuid4()), "expected_version": claimed["version"],
            "facts_patch": {"device_ref": "DEMO-01", "occurred_at": "2026-11-18T10:00:00+08:00"}}
    path = f"/api/v1/human-tasks/{paused['human_task_id']}/resume"
    response = client.post(path, json=body)
    assert response.status_code == 202, response.text
    assert client.post(path, json=body).json() == response.json()
    assert run_once(run_id)
    ready = detail(client, created["ticket_id"])
    assert ready["status"] == "PENDING_CONFIRMATION"
    assert ready["solution_json"]["data_source"] == "mock"
    assert ready["human_task_id"] is None
    reviewed = action(client, f"tickets/{created['ticket_id']}/review", ready["version"], decision="approve")
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "PENDING_CONFIRMATION"
    contacted = action(client, f"tickets/{created['ticket_id']}/customer-feedback", reviewed.json()["version"], outcome="contacted", reason="人工已联系模拟客户")
    assert contacted.status_code == 200 and contacted.json()["status"] == "WAITING_CUSTOMER"
    closed = action(client, f"tickets/{created['ticket_id']}/close", contacted.json()["version"], outcome="resolved", reason="人工核验模拟问题已解决")
    assert closed.status_code == 200, closed.text
    final = detail(client, created["ticket_id"])
    assert final["status"] == "RESOLVED" and final["active_run_id"] is None
    with Session(test_engine) as db:
        assert db.get(Run, run_id).thread_id == str(run_id)
        assert db.get(HumanAction, UUID(body["action_id"])).consumed_at is not None
        assert db.scalar(select(func.count()).select_from(ToolExecution).where(ToolExecution.run_id == run_id)) == 2
        assert db.scalar(select(func.count()).select_from(NodeRun).where(NodeRun.run_id == run_id)) >= 8


def test_complete_input_gets_proposal_without_human_pause(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    assert run_once(UUID(created["run_id"]))
    value = detail(client, created["ticket_id"])
    assert value["status"] == "PENDING_CONFIRMATION"
    assert value["human_task_id"] is None
    with Session(test_engine) as db:
        parsed = db.scalar(select(NodeRun).where(NodeRun.run_id == UUID(created["run_id"]), NodeRun.node_name == "parse_request"))
        assert parsed.input_refs["case_version"] == created["version"] + 1
    assert not run_once(UUID(created["run_id"]))


def worker_command(run_id, mode="worker"):
    return [sys.executable, "-m", "app.workers.runtime", mode, "--once", "--run-id", str(run_id)]


def child_worker(run_id, mode="worker"):
    deadline = time.monotonic() + 15
    while True:
        result = subprocess.run(worker_command(run_id, mode), capture_output=True, text=True, timeout=35)
        assert result.returncode == 0, result.stderr
        if json.loads(result.stdout)["processed"]:
            return result.stdout
        with Session(get_engine()) as db:
            pending = db.scalar(select(ExecutionTask.id).join(Run).where(
                ExecutionTask.run_id == UUID(str(run_id)), Run.status.in_(["queued", "running"]),
                ExecutionTask.status.in_(["running"] if mode == "reconcile" else ["queued", "running"]),
            ).limit(1))
        if pending is None:
            return result.stdout  # 已完成/暂停时的一次空轮询仍须保持幂等。
        assert time.monotonic() < deadline, "待执行任务在限定时间内未能被领取"
        time.sleep(0.1)


def test_worker_can_wait_for_future_task_availability(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with Session(test_engine) as db:
        db.execute(update(ExecutionTask).where(ExecutionTask.run_id == run_id)
                   .values(available_at=func.clock_timestamp() + timedelta(seconds=5)))
        db.commit()
    # 同数据库时钟回拨后的状态：一次轮询允许暂时没有可领取任务。
    assert not run_once(run_id)
    assert json.loads(child_worker(run_id))["processed"]
    assert detail(client, created["ticket_id"])["status"] == "PENDING_CONFIRMATION"


@contextmanager
def held_worker(run_id, point):
    environment = {**os.environ, "CASEPILOT_TEST_FAILPOINT": point}
    command = worker_command(run_id)
    command.remove("--once")  # 使用正常轮询；短暂时钟回拨或锁竞争不等于任务处理失败。
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, env=environment)
    lines, received = [], queue.Queue()

    def reader():
        for line in process.stdout:
            lines.append(line)
            if line.strip() == f"P02_FAILPOINT:{point}":
                received.put(True)
        received.put(False)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        assert received.get(timeout=20), "".join(lines)
        yield process
    finally:
        if process.poll() is None:
            process.kill()  # 真正终止独立 Worker 进程，而不是模拟异常返回。
        process.wait(timeout=10)
        thread.join(timeout=2)
        process.stdout.close()


def expire_lease(engine, run_id):
    with Session(engine) as db:
        db.execute(update(ExecutionTask).where(ExecutionTask.run_id == UUID(str(run_id)), ExecutionTask.status == "running")
                   .values(lease_until=func.clock_timestamp() - timedelta(seconds=1)))
        db.commit()


@pytest.mark.parametrize("point", ["after_claim", "after_interrupt_checkpoint"])
def test_force_kill_before_projection_recovers_to_one_human_task(api, test_engine, point):
    client, _, _ = api
    created = create(client)
    run_id = UUID(created["run_id"])
    with held_worker(run_id, point):
        assert detail(client, created["ticket_id"])["status"] == "RUNNING"
    expire_lease(test_engine, run_id)
    child_worker(run_id, "reconcile")
    if point == "after_claim":
        assert detail(client, created["ticket_id"])["status"] == "RUNNING"
        child_worker(run_id)
    paused = detail(client, created["ticket_id"])
    assert paused["status"] == "WAITING_HUMAN"
    child_worker(run_id, "reconcile")
    child_worker(run_id)
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(HumanTask).where(HumanTask.run_id == run_id)) == 1


def test_force_kill_after_tool_result_reuses_cached_logical_action(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with held_worker(run_id, "after_tool_write"):
        with Session(test_engine) as db:
            original_tool = db.scalar(select(ToolExecution).where(ToolExecution.run_id == run_id))
            assert original_tool is not None
            original_id = original_tool.id
    expire_lease(test_engine, run_id)
    child_worker(run_id, "reconcile")
    child_worker(run_id)
    assert detail(client, created["ticket_id"])["status"] == "PENDING_CONFIRMATION"
    with Session(test_engine) as db:
        tools = list(db.scalars(select(ToolExecution).where(ToolExecution.run_id == run_id)))
        assert len(tools) == 2 and original_id in {tool.id for tool in tools}


def test_force_kill_after_graph_completion_projects_saved_solution(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with held_worker(run_id, "after_finish_checkpoint"):
        assert detail(client, created["ticket_id"])["status"] == "RUNNING"
    expire_lease(test_engine, run_id)
    child_worker(run_id, "reconcile")
    assert detail(client, created["ticket_id"])["status"] == "PENDING_CONFIRMATION"
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(ToolExecution).where(ToolExecution.run_id == run_id)) == 2


def test_consumed_resume_is_not_sent_again_at_next_interrupt(api, test_engine):
    client, _, _ = api
    created = create(client)
    run_id = UUID(created["run_id"])
    child_worker(run_id)
    first = detail(client, created["ticket_id"])
    claimed = claim(client, first)
    body = {"action_id": str(uuid4()), "expected_version": claimed["version"], "facts_patch": {"device_ref": "DEMO-01"}}
    response = client.post(f"/api/v1/human-tasks/{first['human_task_id']}/resume", json=body)
    assert response.status_code == 202
    with held_worker(run_id, "after_resume_checkpoint"):
        pass
    expire_lease(test_engine, run_id)
    child_worker(run_id, "reconcile")
    child_worker(run_id)
    second = detail(client, created["ticket_id"])
    assert second["status"] == "WAITING_HUMAN" and second["human_task_id"] != first["human_task_id"]
    human_task = client.get(f"/api/v1/human-tasks/{second['human_task_id']}").json()
    assert human_task["payload_json"]["missing_fields"] == ["occurred_at"]
    with Session(test_engine) as db:
        assert db.get(HumanAction, UUID(body["action_id"])).consumed_at is not None
        assert db.get(HumanTask, UUID(first["human_task_id"])).status == "completed"
        assert db.scalar(select(func.count()).select_from(ExecutionTask).where(ExecutionTask.run_id == run_id, ExecutionTask.kind == "resume")) == 1
    # 旧 HTTP 动作可幂等重放，但绝不能恢复新的暂停点。
    assert client.post(f"/api/v1/human-tasks/{first['human_task_id']}/resume", json=body).json() == response.json()
    assert detail(client, created["ticket_id"])["human_task_id"] == second["human_task_id"]
    claimed_second = claim(client, second)
    resumed = action(client, f"human-tasks/{second['human_task_id']}/resume", claimed_second["version"], facts_patch={"occurred_at": "2026-11-18T10:00:00Z"})
    assert resumed.status_code == 202
    child_worker(run_id)
    assert detail(client, created["ticket_id"])["status"] == "PENDING_CONFIRMATION"


def test_expired_lease_cannot_bypass_live_run_lock(api, test_engine):
    client, _, _ = api
    created = create(client)
    run_id = UUID(created["run_id"])
    with held_worker(run_id, "after_claim"):
        expire_lease(test_engine, run_id)
        with Session(test_engine) as db:
            token = db.get(ExecutionTask, UUID(created["task_id"])).lease_token
        assert not run_once(run_id)
        assert not run_once(run_id, reconcile=True)
        with Session(test_engine) as db:
            assert db.get(ExecutionTask, UUID(created["task_id"])).lease_token == token
    expire_lease(test_engine, run_id)
    child_worker(run_id)
    assert detail(client, created["ticket_id"])["status"] == "WAITING_HUMAN"


def test_takeover_rejects_late_projection_and_waits_for_lock_release(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with held_worker(run_id, "after_finish_checkpoint"):
        current = detail(client, created["ticket_id"])
        stopped = action(client, f"tickets/{created['ticket_id']}/takeover", current["version"], reason="人工要求接管")
        assert stopped.status_code == 202
        assert detail(client, created["ticket_id"])["cancel_requested"] is True
        assert not run_once(run_id)
        assert action(client, f"tickets/{created['ticket_id']}/close", stopped.json()["version"], outcome="resolved", reason="尚未停止").status_code == 409
    # 模拟旧执行释放锁后恢复，不能把已经落检查点的迟到方案直接投影成待确认。
    child_worker(run_id)
    paused = detail(client, created["ticket_id"])
    assert paused["status"] == "WAITING_HUMAN" and paused["solution_json"] == {}
    assert not paused["cancel_requested"]
    task = client.get(f"/api/v1/human-tasks/{paused['human_task_id']}").json()
    assert task["reason_code"] == "TAKEOVER_REQUESTED"


def test_claim_ownership_stale_versions_and_manual_unresolved_close(api, test_engine, account_factory):
    client, _, _ = api
    created = create(client)
    run_id = UUID(created["run_id"])
    run_once(run_id)
    paused = detail(client, created["ticket_id"])
    claimed = claim(client, paused)
    other_user, password = account_factory()
    with TestClient(app) as other:
        logged_in = other.post("/api/v1/auth/login", json={"login": other_user.login, "password": password})
        other.headers["X-CSRF-Token"] = logged_in.json()["csrf_token"]
        assert action(other, f"human-tasks/{paused['human_task_id']}/claim", claimed["version"]).status_code == 409
        assert action(other, f"human-tasks/{paused['human_task_id']}/resume", claimed["version"], facts_patch={"device_ref": "D"}).status_code == 403
    assert action(client, f"human-tasks/{paused['human_task_id']}/resume", paused["version"], facts_patch={"device_ref": "D"}).status_code == 409
    closed = action(client, f"tickets/{created['ticket_id']}/close", claimed["version"], outcome="unresolved", reason="人工确认当前资料不足，关闭模拟工单")
    assert closed.status_code == 200 and closed.json()["status"] == "CLOSED_UNRESOLVED"
    with Session(test_engine) as db:
        assert db.get(HumanTask, UUID(paused["human_task_id"])).status == "cancelled"
    assert not run_once(run_id)


def test_reinvestigation_creates_new_thread_and_retains_old_trace(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="OLD-01", occurred_at="2026-11-18T10:00:00Z")
    old_id = UUID(created["run_id"])
    run_once(old_id)
    before = detail(client, created["ticket_id"])
    response = action(client, f"tickets/{created['ticket_id']}/reinvestigate", before["version"], reason="人工修正设备", facts_patch={"device_ref": "NEW-01"})
    assert response.status_code == 202, response.text
    new_id = UUID(response.json()["run_id"])
    assert new_id != old_id
    run_once(new_id)
    with Session(test_engine) as db:
        assert db.get(Run, old_id).status == "superseded"
        assert db.get(Run, old_id).thread_id != db.get(Run, new_id).thread_id
        assert db.scalar(select(func.count()).select_from(NodeRun).where(NodeRun.run_id == old_id)) > 0
    assert detail(client, created["ticket_id"])["device_ref"] == "NEW-01"


def test_step_budget_and_cross_epoch_limit_end_in_human(api, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(get_settings(), "max_mock_steps", 1)
    monkeypatch.setattr(get_settings(), "max_budget_epochs", 1)
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z")
    run_once(UUID(created["run_id"]))
    paused = detail(client, created["ticket_id"])
    task = client.get(f"/api/v1/human-tasks/{paused['human_task_id']}").json()
    assert task["reason_code"] == "BUDGET_EXHAUSTED"
    claimed = claim(client, paused)
    assert action(client, f"human-tasks/{paused['human_task_id']}/resume", claimed["version"], facts_patch={}).status_code == 409


def test_mock_tool_error_creates_visible_human_task(api):
    client, _, _ = api
    created = create(client, device_ref="DEMO-01", occurred_at="2026-11-18T10:00:00Z", feedback_text="[MOCK_ERROR]")
    run_once(UUID(created["run_id"]))
    paused = detail(client, created["ticket_id"])
    assert paused["status"] == "WAITING_HUMAN"
    task = client.get(f"/api/v1/human-tasks/{paused['human_task_id']}").json()
    assert task["reason_code"] == "MOCK_TOOL_ERROR"


def test_revoked_execution_cannot_project_its_saved_solution(api):
    client, _, _ = api
    created = create(client, device_ref="D", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with checkpoint_connection() as connection:
        assert try_run_lock(connection, run_id)
        ctx, initial, _, _, _ = claim_task(connection, eligible_tasks(run_id)[0])
        graph = build_graph(PostgresSaver(connection), ctx)
        config = {"configurable": {"thread_id": str(run_id)}}
        graph.invoke({**initial, "budget_epoch": 0, "completed_steps": [], "consumed_action_ids": []}, config, durability="sync")
        saved = graph.get_state(config)
        current = detail(client, created["ticket_id"])
        assert action(client, f"tickets/{created['ticket_id']}/takeover", current["version"], reason="接管已生成但未投影的结果").status_code == 202
        with pytest.raises(LeaseLost):
            project_result(ctx, saved)
        assert detail(client, created["ticket_id"])["solution_json"] == {}
    child_worker(run_id)
    assert detail(client, created["ticket_id"])["status"] == "WAITING_HUMAN"


def test_lost_checkpoint_connection_stops_old_execution(api, test_engine):
    client, _, _ = api
    created = create(client)
    run_id = UUID(created["run_id"])
    with checkpoint_connection() as connection:
        assert try_run_lock(connection, run_id)
        ctx, _, _, _, _ = claim_task(connection, eligible_tasks(run_id)[0])
        connection.close()
        with Session(test_engine) as db, pytest.raises(LeaseLost):
            ctx.fenced(db)
    expire_lease(test_engine, run_id)
    child_worker(run_id)
    assert detail(client, created["ticket_id"])["status"] == "WAITING_HUMAN"


def test_unsupported_graph_version_preserves_request_for_reinvestigation(api, test_engine):
    client, _, _ = api
    created = create(client, device_ref="D", occurred_at="2026-11-18T10:00:00Z")
    run_id = UUID(created["run_id"])
    with Session(test_engine) as db:
        db.execute(update(Run).where(Run.id == run_id).values(graph_version="unsupported-v0"))
        db.commit()
    assert run_once(run_id)
    paused = detail(client, created["ticket_id"])
    claimed = claim(client, paused)
    blocked = action(client, f"human-tasks/{paused['human_task_id']}/resume", claimed["version"], facts_patch={})
    assert blocked.status_code == 409
    again = action(client, f"tickets/{created['ticket_id']}/reinvestigate", claimed["version"], reason="换用当前图版本")
    assert again.status_code == 202
    child_worker(UUID(again.json()["run_id"]))
    assert detail(client, created["ticket_id"])["status"] == "PENDING_CONFIRMATION"


def test_heartbeat_renews_owned_lease(api, test_engine, monkeypatch):
    client, _, _ = api
    monkeypatch.setattr(get_settings(), "worker_lease_seconds", 3)
    created = create(client)
    run_id = UUID(created["run_id"])
    with checkpoint_connection() as connection:
        assert try_run_lock(connection, run_id)
        ctx, _, _, _, _ = claim_task(connection, eligible_tasks(run_id)[0])
        with Session(test_engine) as db:
            original = db.get(ExecutionTask, ctx.task_id).lease_until
        with Heartbeat(ctx):
            renewed = original
            for _ in range(30):
                threading.Event().wait(0.1)
                with Session(test_engine) as db:
                    renewed = db.get(ExecutionTask, ctx.task_id).lease_until
                if renewed > original:
                    break
            assert renewed > original and not ctx.lost.is_set()
            assert ctx.control({}) is None
    expire_lease(test_engine, run_id)
    child_worker(run_id)
