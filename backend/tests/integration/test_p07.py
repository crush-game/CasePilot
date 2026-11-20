import json
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.contracts import AgentPolicy
from app.api.schemas import TicketCreate
from app.config import get_settings
from app.domain.enums import Role
from app.knowledge.hybrid import build_index
from app.manage import create_user
from app.providers.ledger import budget_report, create_budget
from app.providers.remote import ProviderSession
from app.repositories.models import HumanTask, NodeRun, Run, Ticket, ToolExecution
from app.services.tickets import create_ticket
from app.services.workflow_common import latest_snapshot
from app.workers.checkpoints import setup_checkpoints
from app.workers.runtime import run_once
from test_p06 import configuration, handler, isolated, seed


pytestmark = pytest.mark.integration


def advance(run_id, provider_session):
    """正式Worker会持续轮询；一次暂未可领取不能当成本次任务已执行。"""
    import time
    deadline = time.monotonic() + 5
    while not run_once(run_id, provider_session=provider_session):
        assert time.monotonic() < deadline, "P07任务在限定时间内未被领取"
        time.sleep(0.05)
    return True


def response(request, mode="sufficient"):
    if not request.url.path.endswith("chat/completions"):
        return handler(request)
    body = json.loads(request.content)
    system, observation = (json.loads(row["content"]) for row in body["messages"])
    schema = system["output_schema"]["title"]
    refs = system["allowed_evidence_refs"]
    common = {"data_source": "mock", "evidence_refs": refs}
    if schema == "ParsedRequest":
        value = {**common, "request_type": "fault" if mode == "fault" else "consultation",
                 "question": observation["question"][:500], "symptoms": [], "unresolved_items": []}
    elif schema == "SupervisorDecision":
        action = "generate_solution" if observation.get("last_subtask") else "knowledge_investigation"
        if mode == "loop":
            action = "knowledge_investigation"
        elif mode == "direct":
            action = "generate_solution"
        elif mode == "fault":
            action = "fault_investigation"
        elif mode == "human":
            action = "human_interrupt"
        elif mode == "partial" and (observation.get("last_subtask") or {}).get("status") == "partial":
            action = "knowledge_investigation"
        value = {**common, "action": action, "reason": "合同测试决定", "goal": "检查连接资料", "query": "连接",
                 "unresolved_items": []}
        if mode == "partial":
            value["query"] = "连接补充" if observation.get("last_subtask") else "连接"
    elif schema == "KnowledgeAssessment":
        value = {**common, "status": "sufficient", "findings": [{"point": "检查连接设置", "applicability": "匹配已确认型号/版本", "evidence_refs": refs[:1]}],
                 "unresolved_items": [], "conflicts": [], "suggested_action": "finish", "rewrite_query": "", "context_refs": []}
        if mode in {"gap", "rewrite"}:
            value.update(status="no_evidence", findings=[], unresolved_items=["缺少直接支持"],
                         suggested_action="rewrite" if mode == "rewrite" else "human", rewrite_query="升级")
        elif mode == "conflict":
            value.update(status="conflicting", conflicts=[refs[:2]], suggested_action="rewrite", rewrite_query="升级")
        elif mode == "context" and observation["remaining_remedies"]["context"]:
            for row in observation["evidence"]:
                neighbors = [row["metadata"].get(name) for name in ("previous_ref", "next_ref")]
                if any(ref and ref not in refs for ref in neighbors):
                    value.update(status="partial", unresolved_items=["缺少相邻步骤"], suggested_action="context", context_refs=[row["ref"]])
                    break
        elif mode == "forged":
            value["findings"][0]["evidence_refs"] = ["kb:00000000000000000000000000000000"]
        elif mode == "partial" and not observation.get("prior_subtasks"):
            value.update(status="partial", unresolved_items=["还缺第二项"], suggested_action="finish")
    else:
        value = {**common, "internal_plan": "按引用步骤核对连接，等待人工验证", "reply_draft": "请检查连接设置并反馈结果。", "reviewed": False}
    return httpx.Response(200, json={"model": body["model"], "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}],
                                    "usage": {"prompt_tokens": 100, "completion_tokens": 100}})


@pytest.fixture
def agent(isolated, monkeypatch, tmp_path):
    # 本组直接测试运行/人工服务，不执行登录；密码算法由既有认证回归覆盖。
    monkeypatch.setattr("app.manage.hash_password", lambda _: "p07-no-login-contract-fixture")
    config = configuration()
    path = tmp_path / "provider-contract.json"
    path.write_text(config.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("AFTERSALES_WORKFLOW_GRAPH_VERSION", "supervisor-v1")
    monkeypatch.setenv("AFTERSALES_PROVIDER_CONFIG_PATH", str(path))
    get_settings.cache_clear()
    setup_checkpoints()
    def session(mode="sufficient", **caps):
        return ProviderSession(isolated, create_budget(isolated, scope="p07-contract", max_calls=caps.pop("max_calls", 20), **caps), config,
                               SecretStr("CONTRACT_TEST_KEY"), transport=httpx.MockTransport(lambda request: response(request, mode)))
    def create(**changes):
        with Session(isolated, expire_on_commit=False) as db:
            user = create_user(db, "p07_" + uuid4().hex, "contract-password-only", Role.BUSINESS)
            created = create_ticket(db, user, str(uuid4()), TicketCreate.model_validate({"feedback_text": "连接如何检查？",
                "customer_email": "synthetic@example.test", "product_ref": "P06", "firmware_version": "1.0", **changes}))
        return created, user
    def inspect(created):
        with Session(isolated) as db:
            run = db.get(Run, UUID(created["run_id"]))
            ticket = db.get(Ticket, UUID(created["ticket_id"]))
            return ticket.status, run.stop_reason, latest_snapshot(db, run.id), list(db.scalars(select(NodeRun.node_name).where(NodeRun.run_id == run.id)))
    return isolated, session, create, inspect


def prepare(engine, session, *, long=False):
    import asyncio
    seed(engine, "\n\n".join("连接检查步骤" * 110 for _ in range(12)) if long else "连接检查设置并反馈结果。")
    seed(engine, "连接资料第二条。", key="p07-other")
    asyncio.run(build_index(session))


def test_supervisor_and_checkpointed_child_produce_grounded_draft(agent):
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, _ = create()
    assert advance(UUID(created["run_id"]), provider_session=provider)
    status, reason, state, names = inspect(created)
    assert status == "PENDING_CONFIRMATION" and reason is None
    assert state["graph_version"] == "supervisor-v1" and state["inference_mode"] == "contract"
    assert state["knowledge_report"]["status"] == "completed" and state["knowledge_report"]["findings"]
    assert {"knowledge.begin", "knowledge.search", "knowledge.assess", "knowledge.finish"} <= set(names)
    assert state["solution"]["evidence_refs"] and not state["solution"]["reviewed"]
    before = budget_report(engine, provider.budget_id)["calls_used"]
    assert not run_once(UUID(created["run_id"]), provider_session=provider)
    assert budget_report(engine, provider.budget_id)["calls_used"] == before


def test_future_available_task_is_polled_before_asserting_result(agent):
    from datetime import timedelta
    from sqlalchemy import func, update
    from app.repositories.models import ExecutionTask
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, _ = create()
    run_id = UUID(created["run_id"])
    with Session(engine) as db:
        db.execute(update(ExecutionTask).where(ExecutionTask.run_id == run_id)
                   .values(available_at=func.clock_timestamp() + timedelta(seconds=0.3)))
        db.commit()
    assert not run_once(run_id, provider_session=provider)
    assert advance(run_id, provider)
    assert inspect(created)[0] == "PENDING_CONFIRMATION"


@pytest.mark.parametrize("mode,expected", [("direct", "INSUFFICIENT_EVIDENCE"), ("human", "MODEL_REQUESTED_HUMAN"),
    ("fault", "FAULT_TOOLS_NOT_READY"), ("gap", "KNOWLEDGE_GAP"), ("rewrite", "NO_PROGRESS"),
    ("conflict", "KNOWLEDGE_CONFLICT"), ("forged", "UNTRUSTED_MODEL_EVIDENCE"), ("loop", "NO_PROGRESS")])
def test_supervisor_hard_guards_and_no_progress_stop_in_human(agent, mode, expected):
    engine, session, create, inspect = agent
    provider = session(mode)
    prepare(engine, provider)
    created, _ = create()
    assert advance(UUID(created["run_id"]), provider_session=provider)
    status, reason, state, names = inspect(created)
    assert status == "WAITING_HUMAN" and reason == expected
    assert not state.get("solution") and budget_report(engine, provider.budget_id)["calls_used"] <= 20
    with Session(engine) as db:
        task = db.scalar(select(HumanTask).where(HumanTask.run_id == UUID(created["run_id"])))
        assert task.payload_json["reason_code"] == expected


def test_context_only_fetches_actual_neighbors_once(agent):
    engine, session, create, inspect = agent
    provider = session("context")
    prepare(engine, provider, long=True)
    created, _ = create()
    advance(UUID(created["run_id"]), provider_session=provider)
    status, reason, state, names = inspect(created)
    assert status == "PENDING_CONFIRMATION" and names.count("knowledge.context") == 1, (reason, names)
    assert state["knowledge_contexts"] == 1


def test_missing_scope_pauses_and_trusted_human_resume_keeps_same_thread(agent):
    from app.api.schemas import ResumeInput, VersionedAction
    from app.services.human import claim, resume
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, user = create(firmware_version=None)
    run_id = UUID(created["run_id"])
    advance(run_id, provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "MISSING_FACTS")
    with Session(engine) as db:
        task = db.scalar(select(HumanTask).where(HumanTask.run_id == run_id))
        ticket = db.get(Ticket, UUID(created["ticket_id"]))
        claimed = claim(db, user, task.id, VersionedAction(action_id=uuid4(), expected_version=ticket.version))
        resume(db, user, task.id, ResumeInput(action_id=uuid4(), expected_version=claimed["version"], facts_patch={"firmware_version": "1.0"}))
    advance(run_id, provider_session=session())
    assert inspect(created)[0] == "PENDING_CONFIRMATION"
    assert inspect(created)[2]["budget_epoch"] == 1


@pytest.mark.parametrize("cap,expected_calls", [({"max_calls": 2}, 2), ({"max_tokens": 1}, 0), ({"max_cost": 0.00000001}, 0)])
def test_parent_child_share_physical_call_token_and_cost_budget(agent, cap, expected_calls):
    engine, session, create, inspect = agent
    prepare(engine, session())
    provider = session(**cap)
    created, _ = create()
    advance(UUID(created["run_id"]), provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "PROVIDER_BUDGET_EXHAUSTED")
    assert budget_report(engine, provider.budget_id)["calls_used"] == expected_calls


def test_model_timeout_is_bounded_and_projects_human_task(agent):
    engine, session, create, inspect = agent
    provider = session()
    def timeout(request):
        raise httpx.ReadTimeout("CONTRACT_TEST_KEY should never be echoed")
    provider.transport = httpx.MockTransport(timeout)
    created, _ = create()
    advance(UUID(created["run_id"]), provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "PROVIDER_TIMEOUT")
    report = budget_report(engine, provider.budget_id)
    assert report["calls_used"] == 2 and "CONTRACT_TEST_KEY" not in json.dumps(report)


def test_public_profile_is_pinned_to_created_run(agent, monkeypatch, tmp_path):
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, _ = create()
    replacement = configuration().model_copy(update={"config_version": "changed-after-create"})
    path = tmp_path / "changed.json"
    path.write_text(replacement.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("AFTERSALES_PROVIDER_CONFIG_PATH", str(path))
    get_settings.cache_clear()
    advance(UUID(created["run_id"]), provider_session=provider)
    assert inspect(created)[0] == "PENDING_CONFIRMATION"
    assert inspect(created)[2]["agent_config"]["providers"]["config_version"] == "contract-v1"


def policy_for(engine, created, **changes):
    from app.repositories.models import CaseSnapshot
    from app.services.tickets import digest
    with Session(engine) as db:
        row = db.scalar(select(CaseSnapshot).where(CaseSnapshot.run_id == UUID(created["run_id"])))
        state = {**row.state_json, "agent_config": {**row.state_json["agent_config"],
            "policy": {**row.state_json["agent_config"]["policy"], **changes}}}
        row.state_json, row.checksum = state, digest(state)
        db.commit()


def test_pinned_deadline_survives_reclaim_without_refresh(agent):
    from datetime import timedelta
    from sqlalchemy import func
    engine, session, create, inspect = agent
    provider = session()
    created, _ = create()
    policy_for(engine, created, timeout_seconds=1)
    with Session(engine) as db:
        run = db.get(Run, UUID(created["run_id"]))
        run.budget_json = {"budget_epoch": 0, "epoch_started_at": (db.scalar(select(func.clock_timestamp())) - timedelta(seconds=10)).isoformat()}
        db.commit()
    advance(UUID(created["run_id"]), provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "BUDGET_EXHAUSTED")
    assert budget_report(engine, provider.budget_id)["calls_used"] == 0


def test_context_and_search_share_durable_tool_budget(agent):
    engine, session, create, inspect = agent
    provider = session("context")
    prepare(engine, provider, long=True)
    created, _ = create()
    policy_for(engine, created, max_tools=1)
    advance(UUID(created["run_id"]), provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "TOOL_BUDGET_EXHAUSTED")


def test_human_new_epoch_cannot_reset_cross_epoch_call_limit(agent):
    from app.api.schemas import ResumeInput, VersionedAction
    from app.services.human import claim, resume
    engine, session, create, inspect = agent
    prepare(engine, session())
    provider = session()
    created, user = create(firmware_version=None)
    policy_for(engine, created, max_run_calls=2)
    run_id = UUID(created["run_id"])
    advance(run_id, provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "MISSING_FACTS")
    with Session(engine) as db:
        task = db.scalar(select(HumanTask).where(HumanTask.run_id == run_id, HumanTask.status == "unclaimed"))
        ticket = db.get(Ticket, UUID(created["ticket_id"]))
        claimed = claim(db, user, task.id, VersionedAction(action_id=uuid4(), expected_version=ticket.version))
        resume(db, user, task.id, ResumeInput(action_id=uuid4(), expected_version=claimed["version"], facts_patch={"firmware_version": "1.0"}))
    next_provider = session()
    advance(run_id, provider_session=next_provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "BUDGET_EXHAUSTED")
    assert budget_report(engine, next_provider.budget_id)["calls_used"] == 0


def test_partial_subtask_keeps_findings_and_sources_for_next_delegation(agent):
    engine, session, create, inspect = agent
    provider = session("partial")
    prepare(engine, provider)
    created, _ = create()
    advance(UUID(created["run_id"]), provider_session=provider)
    status, reason, state, _ = inspect(created)
    assert status == "PENDING_CONFIRMATION", reason
    assert [row["result"]["status"] for row in state["knowledge_history"]] == ["partial", "completed"]
    assert state["knowledge_history"][0]["result"]["findings"]
    assert set(state["knowledge_history"][0]["result"]["evidence_refs"]) <= set(state["evidence_refs"])


def test_run_endpoint_orders_child_steps_by_logical_sequence(agent):
    from datetime import timedelta
    from sqlalchemy import func
    from app.api.routes import get_run
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, actor = create()
    run_id = UUID(created["run_id"])
    advance(run_id, provider_session=provider)
    expected = [step["node_name"] for step in inspect(created)[2]["completed_steps"]]
    with Session(engine) as db:
        now = db.scalar(select(func.clock_timestamp()))
        for node in db.scalars(select(NodeRun).where(NodeRun.run_id == run_id)):
            position = int(node.logical_step_id.rsplit(":", 1)[-1])
            node.created_at = now - timedelta(seconds=position)
        db.commit()
        actual = get_run(run_id, actor, db)
        assert [node["node_name"] for node in actual.nodes] == expected


def test_archived_source_during_solution_call_is_rejected_before_projection(agent):
    from app.knowledge.schemas import KnowledgeAction
    from app.repositories.models import AppUser, KBDocument
    from app.services.knowledge import archive
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    def late(request):
        result = response(request)
        if request.url.path.endswith("chat/completions"):
            system = json.loads(json.loads(request.content)["messages"][0]["content"])
            if system["output_schema"]["title"] == "SolutionDraft":
                with Session(engine) as db:
                    for doc in list(db.scalars(select(KBDocument).where(KBDocument.status == "active"))):
                        archive(db, db.get(AppUser, doc.created_by), doc.id, KnowledgeAction(
                            action_id=uuid4(), expected_revision=doc.revision, reason="contract-late-change"))
        return result
    provider.transport = httpx.MockTransport(late)
    created, _ = create()
    advance(UUID(created["run_id"]), provider_session=provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "EVIDENCE_NOT_APPLICABLE")
    with Session(engine) as db:
        assert not db.get(Ticket, UUID(created["ticket_id"])).solution_json


@pytest.mark.parametrize("point,expected", [("after_agent_action_write", "PENDING_CONFIRMATION"),
    ("after_agent_search_write", "PENDING_CONFIRMATION"), ("before_agent_request", "WAITING_HUMAN")])
def test_real_process_kill_reuses_actions_or_stops_unknown_outcome(agent, point, expected):
    from contextlib import contextmanager
    from datetime import timedelta
    import os
    import queue
    import subprocess
    import sys
    import threading
    from sqlalchemy import func, update
    from app.repositories.models import ExecutionTask
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, _ = create()
    run_id = UUID(created["run_id"])
    process = subprocess.Popen([sys.executable, "tests/helpers/p07_worker.py", str(run_id), str(provider.budget_id)],
        env={**os.environ, "CASEPILOT_TEST_FAILPOINT": point}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    received, lines = queue.Queue(), []
    def read():
        for line in process.stdout:
            lines.append(line)
            if line.strip() == f"P02_FAILPOINT:{point}":
                received.put(True)
        received.put(False)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        assert received.get(timeout=30), "".join(lines)
        with Session(engine) as db:
            db.execute(update(ExecutionTask).where(ExecutionTask.run_id == run_id)
                .values(lease_until=func.clock_timestamp() - timedelta(seconds=1)))
            db.commit()
        assert not run_once(run_id, provider_session=provider)  # 仍持运行锁的旧进程不能被抢占。
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        reader.join(timeout=2)
        process.stdout.close()
    with Session(engine) as db:
        successful = list(db.scalars(select(ToolExecution.logical_action_id).where(ToolExecution.run_id == run_id,
                                                                                 ToolExecution.status == "succeeded")))
    used = budget_report(engine, provider.budget_id)["calls_used"]
    advance(run_id, provider_session=provider)
    assert inspect(created)[0] == expected
    if expected == "WAITING_HUMAN":
        assert inspect(created)[1] == "ACTION_OUTCOME_UNKNOWN"
        assert budget_report(engine, provider.budget_id)["calls_used"] == used
    else:
        with Session(engine) as db:
            assert all(db.scalar(select(ToolExecution.id).where(ToolExecution.run_id == run_id,
                ToolExecution.logical_action_id == identifier, ToolExecution.status == "succeeded")) for identifier in successful)
        # 成功路径仅5次聊天和2次检索服务调用，另有准备索引的1次调用。
        assert budget_report(engine, provider.budget_id)["calls_used"] == 8
