from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.schemas import TicketCreate
from app.config import get_settings
from app.domain.enums import Role
from app.faults.source import FIXTURE_ROOT
from app.manage import create_user
from app.providers.ledger import create_budget, budget_report
from app.providers.remote import ProviderSession
from app.repositories.models import HumanTask, LogArtifact, LogEvidence, NodeRun, Run, Ticket, ToolExecution
from app.services.tickets import create_ticket
from app.services.workflow_common import latest_snapshot
from app.workers.checkpoints import checkpoint_connection, setup_checkpoints, try_run_lock
from app.workers.runtime import claim_task, eligible_tasks
from test_p06 import configuration, isolated
from test_p07 import advance, response as p07_response


pytestmark = pytest.mark.integration


def response(request, mode="cross"):
    if not request.url.path.endswith("chat/completions"):
        return p07_response(request)
    body = json.loads(request.content)
    system, observation = (json.loads(row["content"]) for row in body["messages"])
    schema, refs = system["output_schema"]["title"], system["allowed_evidence_refs"]
    common = {"data_source": "mock", "evidence_refs": refs}
    if schema == "ParsedRequest":
        value = {**common, "request_type": "fault", "question": observation["question"][:500], "symptoms": [], "unresolved_items": []}
    elif schema == "InvestigationDecision":
        value = {**common, "action": "generate_solution" if observation.get("fault_report") else "fault_investigation",
                 "reason": "根据已取得故障证据选择后续动作", "query": "", "goal": "核对故障窗口内的领域观察",
                 "unresolved_items": [], "fault_domains": ["wifi", "ota"] if mode in {"cross", "repeat", "forged"} else ["ota"] if mode == "ota" else ["wifi"]}
    elif schema == "FaultDecision":
        choices = observation["allowed_actions"]
        action, domain = "human", None
        for possible in ("get_feedbacks", "download_log", "get_wifi_telemetry", "extract_log_window", "finish"):
            if possible in choices:
                action = possible
                break
        else:
            evidence_domains = {row["metadata"]["domain"] for row in observation["evidence"]}
            if "diagnose_wifi" in choices and "wifi" in evidence_domains:
                action = "diagnose_wifi"
            elif "analyze_domain" in choices:
                remaining = [item for item in observation["task"]["domains"] if item not in observation["domain_reports"]]
                domain = remaining[0]
                action = "expand_window" if domain not in evidence_domains and "expand_window" in choices else "analyze_domain"
        value = {**common, "action": action, "domain": domain, "reason": "契约替身按当前观察选择受控动作"}
        if mode == "illegal":
            value["action"] = "download_arbitrary_url"
        if mode == "repeat" and "analyze_domain" in choices:
            value.update(action="analyze_domain", domain="wifi")
    elif schema == "FaultAnalysis":
        value = {**common, "domain": observation["domain"], "findings": [{"point": "窗口内可见升级记录，不能据此确认断连原因。",
            "applicability": "仅覆盖指定领域与查看范围", "evidence_refs": refs[:1]}],
            "candidate_causes": [{"hypothesis": "需要核对升级前后的设备状态", "supporting_refs": refs[:1],
                "contradicting_refs": [], "required_verification": "结合升级结果和连接日志人工验证", "confirmation": "unconfirmed"}],
            "limitations": ["时间先后不证明因果。"]}
        if mode == "forged":
            value["candidate_causes"][0]["contradicting_refs"] = ["logev:" + "0" * 32]
    else:
        return p07_response(request)
    return httpx.Response(200, json={"model": body["model"], "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(value)}}],
                                    "usage": {"prompt_tokens": 100, "completion_tokens": 100}})


@pytest.fixture
def fault_agent(isolated, monkeypatch, tmp_path):
    monkeypatch.setattr("app.manage.hash_password", lambda _: "p08-no-login-contract-fixture")
    data = json.loads((FIXTURE_ROOT / "p08-demo.json").read_text(encoding="utf-8"))
    name = "test-" + uuid4().hex
    path = FIXTURE_ROOT / (name + ".json")
    with path.open("x", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)
    config = configuration()
    config_path = tmp_path / "provider.json"
    config_path.write_text(config.model_dump_json(), encoding="utf-8")
    monkeypatch.setenv("AFTERSALES_WORKFLOW_GRAPH_VERSION", "supervisor-v2")
    monkeypatch.setenv("AFTERSALES_ENTERPRISE_MOCK_FIXTURE", name)
    monkeypatch.setenv("AFTERSALES_PROVIDER_CONFIG_PATH", str(config_path))
    get_settings.cache_clear()
    setup_checkpoints()
    def provider(mode="cross"):
        return ProviderSession(isolated, create_budget(isolated, scope="p08-contract", max_calls=20), config,
            SecretStr("CONTRACT_TEST_KEY"), transport=httpx.MockTransport(lambda request: response(request, mode)))
    def create(**changes):
        with Session(isolated, expire_on_commit=False) as db:
            actor = create_user(db, "p08_" + uuid4().hex, "contract-password-only", Role.BUSINESS)
            value = create_ticket(db, actor, str(uuid4()), TicketCreate.model_validate({"feedback_text": "升级后发生断连，请核对WiFi与OTA的日志。",
                "customer_email": "p08-cross@example.test", "device_ref": "P08-A", "product_ref": "PILOT-01", "firmware_version": "1.0",
                "platform": "android", "app_version": "2.0", "occurred_at": "2026-11-20T10:00:00+08:00", **changes}))
        return value, actor
    def inspect(value):
        with Session(isolated) as db:
            run = db.get(Run, UUID(value["run_id"]))
            ticket = db.get(Ticket, UUID(value["ticket_id"]))
            return ticket.status, run.stop_reason, latest_snapshot(db, run.id), list(db.scalars(select(NodeRun.node_name).where(NodeRun.run_id == run.id)))
    try:
        yield isolated, provider, create, inspect, path, data
    finally:
        assert path.parent == FIXTURE_ROOT and path.stem == name
        path.unlink(missing_ok=True)


def test_cross_domain_fault_subgraph_persists_redacted_sources_and_unconfirmed_causes(fault_agent):
    engine, provider, create, inspect, _, _ = fault_agent
    client = provider()
    value, _ = create()
    assert advance(UUID(value["run_id"]), client)
    status, reason, state, nodes = inspect(value)
    assert status == "PENDING_CONFIRMATION", (reason, nodes)
    report = state["fault_report"]
    assert set(report["inspected_domains"]) == {"wifi", "ota"} and report["source_kind"] == "detailed_log"
    assert report["candidate_causes"][0]["confirmation"] == "unconfirmed"
    assert {"fault.begin", "fault.plan", "fault.execute", "fault.analyze", "fault.finish"} <= set(nodes)
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LogArtifact)) == 1
        evidence = list(db.scalars(select(LogEvidence)))
        assert len(evidence) == 3 and all("MOCK_SECRET_P08" not in row.text and "p08-private@" not in row.text for row in evidence)
    assert "MOCK_SECRET_P08" not in json.dumps(state) and not state["solution"]["reviewed"]
    assert budget_report(engine, client.budget_id)["calls_used"] <= 20


@pytest.mark.parametrize("email,mode,expected", [("p08-wifi-none@example.test", "wifi", "TELEMETRY_ONLY"),
    ("p08-ota-none@example.test", "ota", "NO_DETAILED_LOG"), ("p08-old-version@example.test", "wifi", "NO_MATCHING_RECORD"),
    ("unknown@example.test", "wifi", "NO_FEEDBACK"), ("p08-outside@example.test", "wifi", "NO_MATCHING_LOG_WINDOW")])
def test_no_data_paths_are_explicit_and_never_substitute_wifi_for_ota(fault_agent, email, mode, expected):
    engine, provider, create, inspect, _, _ = fault_agent
    client = provider(mode)
    value, _ = create(customer_email=email)
    advance(UUID(value["run_id"]), client)
    assert inspect(value)[:2] == ("WAITING_HUMAN", expected)
    with Session(engine) as db:
        tools = list(db.scalars(select(ToolExecution.tool_name).where(ToolExecution.run_id == UUID(value["run_id"]))))
    assert ("get_wifi_telemetry" in tools) == (expected == "TELEMETRY_ONLY")


@pytest.mark.parametrize("code", ["AUTH_FAILED", "TIMEOUT", "RATE_LIMITED", "DOWNLOAD_FAILED"])
def test_download_errors_are_not_treated_as_no_log(fault_agent, code):
    engine, provider, create, inspect, path, data = fault_agent
    data["tool_errors"]["download_log"] = code
    path.write_text(json.dumps(data), encoding="utf-8")
    value, _ = create()
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", code)
    with Session(engine) as db:
        assert "get_wifi_telemetry" not in list(db.scalars(select(ToolExecution.tool_name)))


def test_multiple_feedbacks_require_owned_human_selection_and_resume(fault_agent):
    from app.api.schemas import ResumeInput, VersionedAction
    from app.domain.errors import AppError
    from app.services.human import claim, resume
    engine, provider, create, inspect, _, _ = fault_agent
    value, actor = create(customer_email="p08-multi@example.test")
    run_id = UUID(value["run_id"])
    advance(run_id, provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", "FEEDBACK_SELECTION_REQUIRED")
    with Session(engine) as db:
        task = db.scalar(select(HumanTask).where(HumanTask.run_id == run_id))
        assert {row["record_id"] for row in task.payload_json["feedback_candidates"]} == {"feedback:multi:a", "feedback:multi:b"}
        ticket = db.get(Ticket, UUID(value["ticket_id"]))
        claimed = claim(db, actor, task.id, VersionedAction(action_id=uuid4(), expected_version=ticket.version))
        with pytest.raises(AppError):
            resume(db, actor, task.id, ResumeInput(action_id=uuid4(), expected_version=claimed["version"], selected_feedback_ref="feedback:cross:a"))
        db.rollback()
        resume(db, actor, task.id, ResumeInput(action_id=uuid4(), expected_version=claimed["version"], selected_feedback_ref="feedback:multi:a"))
    advance(run_id, provider())
    assert inspect(value)[0] == "PENDING_CONFIRMATION"
    assert inspect(value)[2]["selected_feedback_ref"] == "feedback:multi:a"


@contextmanager
def bound_context(value):
    with checkpoint_connection() as connection:
        run_id = UUID(value["run_id"])
        assert try_run_lock(connection, run_id)
        candidate = next(item for item in eligible_tasks(run_id) if item.run_id == run_id)
        ctx, state, _, _, _ = claim_task(connection, candidate)
        yield ctx, state


def test_persisted_artifact_handles_rebind_only_to_their_original_run(fault_agent):
    from app.faults.tools import FaultTools
    engine, _, create, _, _, _ = fault_agent
    first, _ = create()
    with bound_context(first) as (ctx, state):
        adapter = FaultTools(ctx, state)
        downloaded = adapter.call("download_log", {"feedback_ref": "feedback:cross:a"})
        assert downloaded["source"]["query"]["platform"] == "android"
        assert "customer_email" not in downloaded["source"]["query"]
        ref = downloaded["data"]["artifact_ref"]
        # 新工具实例没有进程内downloaded/windows集合，仍可用持久句柄恢复。
        window = FaultTools(ctx, state).call("extract_log_window", {"artifact_ref": ref})
        assert window["status"] == "success" and len(window["data_refs"]) == 3
        assert "MOCK_SECRET_P08" not in json.dumps(window)
        assert adapter.call("download_log", {"feedback_ref": "feedback:multi:a"})["error_code"] == "FEEDBACK_SCOPE_MISMATCH"
        assert adapter.call("download_log", {"customer_email": "other@example.test"})["error_code"] == "INVALID_ARGUMENTS"
    second, _ = create(customer_email="p08-multi@example.test")
    with bound_context(second) as (ctx, state):
        assert FaultTools(ctx, state).call("extract_log_window", {"artifact_ref": ref})["error_code"] == "FORBIDDEN"


def test_log_evidence_read_requires_business_role_and_ticket_owner_reference(fault_agent):
    from fastapi.testclient import TestClient
    from app.api.dependencies import current_user
    from app.main import app
    engine, provider, create, inspect, _, _ = fault_agent
    value, actor = create()
    advance(UUID(value["run_id"]), provider())
    eid = inspect(value)[2]["evidence_refs"][0].removeprefix("logev:")
    path = f"/api/v1/tickets/{value['ticket_id']}/evidence/{eid}"
    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        app.dependency_overrides[current_user] = lambda: actor
        try:
            result = client.get(path)
            assert result.status_code == 200 and result.json()["usable"]
            assert "MOCK_SECRET_P08" not in result.text and "original_bytes" not in result.text
            another, _ = create()
            assert client.get(f"/api/v1/tickets/{another['ticket_id']}/evidence/{eid}").status_code == 404
            with Session(engine, expire_on_commit=False) as db:
                admin = create_user(db, "p08_kb_role", "contract-password-only", Role.KNOWLEDGE_ADMIN)
            app.dependency_overrides[current_user] = lambda: admin
            assert client.get(path).status_code == 403
        finally:
            app.dependency_overrides.pop(current_user, None)


def test_artifact_owner_foreign_key_and_checksum_are_enforced(fault_agent):
    from app.faults.tools import FaultTools
    from sqlalchemy.exc import IntegrityError
    engine, _, create, _, _, _ = fault_agent
    first, _ = create()
    second, _ = create()
    with bound_context(first) as (ctx, state):
        downloaded = FaultTools(ctx, state).call("download_log", {"feedback_ref": "feedback:cross:a"})
        identifier = UUID(downloaded["data"]["artifact_ref"].removeprefix("artifact:"))
        with Session(engine) as db:
            db.add(LogEvidence(artifact_id=identifier, run_id=UUID(second["run_id"]), ticket_id=UUID(second["ticket_id"]),
                member_name="other.log", line_number=1, occurred_at=db.scalar(select(func.clock_timestamp())), domain="wifi", text="x", content_hash="x"))
            with pytest.raises(IntegrityError):
                db.commit()
            db.rollback()
            artifact = db.get(LogArtifact, identifier)
            artifact.original_bytes = b"changed"
            db.commit()
        assert FaultTools(ctx, state).call("extract_log_window", {"artifact_ref": downloaded["data"]["artifact_ref"]})["error_code"] == "ARTIFACT_CORRUPTED"


def test_fixture_change_after_case_creation_does_not_silently_replace_data(fault_agent):
    engine, provider, create, inspect, path, data = fault_agent
    value, _ = create()
    data["fixture_version"] = "changed"
    path.write_text(json.dumps(data), encoding="utf-8")
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", "ENTERPRISE_SOURCE_CHANGED")
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LogArtifact)) == 0


@pytest.mark.parametrize("change", [{"platform": "ios"}, {"firmware_version": "9.0"}, {"app_version": "9.0"},
                                    {"device_ref": "P08-B"}, {"product_ref": "OTHER"}])
def test_feedback_platform_version_device_and_product_do_not_cross(fault_agent, change):
    _, provider, create, inspect, _, _ = fault_agent
    value, _ = create(**change)
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", "NO_MATCHING_RECORD")


def test_ota_without_ota_records_never_uses_wifi_as_ota_evidence(fault_agent):
    engine, provider, create, inspect, path, data = fault_agent
    data["archives"]["archive:cross"][0]["records"] = [item for item in data["archives"]["archive:cross"][0]["records"] if item["domain"] == "wifi"]
    path.write_text(json.dumps(data), encoding="utf-8")
    value, _ = create()
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", "INSUFFICIENT_DOMAIN_EVIDENCE")
    assert "ota" not in inspect(value)[2]["fault_report"]["inspected_domains"]


def test_invalid_model_tool_is_repaired_once_then_human(fault_agent):
    _, provider, create, inspect, _, _ = fault_agent
    value, _ = create()
    advance(UUID(value["run_id"]), provider("illegal"))
    assert inspect(value)[:2] == ("WAITING_HUMAN", "INVALID_MODEL_OUTPUT")


@pytest.mark.parametrize("files,expected", [([{ "name": "../escape.log", "text": "x"}], "UNSAFE_ARCHIVE"),
    ([{"name": "bad.log", "text": "not json"}], "PARSE_FAILED")])
def test_bad_archive_stops_instead_of_falling_back_to_telemetry(fault_agent, files, expected):
    engine, provider, create, inspect, path, data = fault_agent
    data["archives"]["archive:cross"] = files
    path.write_text(json.dumps(data), encoding="utf-8")
    value, _ = create()
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", expected)
    with Session(engine) as db:
        assert "get_wifi_telemetry" not in list(db.scalars(select(ToolExecution.tool_name)))


def test_missing_fault_platform_requires_human_before_data_access(fault_agent):
    from app.api.schemas import ResumeInput, VersionedAction
    from app.services.human import claim, resume
    engine, provider, create, inspect, _, _ = fault_agent
    value, actor = create(platform=None)
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[:2] == ("WAITING_HUMAN", "MISSING_FACTS")
    assert "platform" in inspect(value)[2]["missing_fields"]
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LogArtifact)) == 0
        task = db.scalar(select(HumanTask).where(HumanTask.run_id == UUID(value["run_id"])))
        ticket = db.get(Ticket, UUID(value["ticket_id"]))
        claimed = claim(db, actor, task.id, VersionedAction(action_id=uuid4(), expected_version=ticket.version))
        resume(db, actor, task.id, ResumeInput(action_id=uuid4(), expected_version=claimed["version"], facts_patch={"platform": "android"}))
    advance(UUID(value["run_id"]), provider())
    assert inspect(value)[0] == "PENDING_CONFIRMATION"


@pytest.mark.parametrize("mode,expected", [("repeat", "NO_PROGRESS"), ("forged", "UNTRUSTED_MODEL_EVIDENCE")])
def test_repeated_domain_or_forged_counterevidence_cannot_complete(fault_agent, mode, expected):
    _, provider, create, inspect, _, _ = fault_agent
    value, _ = create()
    advance(UUID(value["run_id"]), provider(mode))
    assert inspect(value)[:2] == ("WAITING_HUMAN", expected)


def test_fault_planning_uses_shared_persistent_call_budget(fault_agent):
    engine, provider, create, inspect, _, _ = fault_agent
    client = provider()
    from app.repositories.models import ProviderBudget
    with Session(engine) as db:
        db.get(ProviderBudget, client.budget_id).max_calls = 3
        db.commit()
    value, _ = create()
    advance(UUID(value["run_id"]), client)
    assert inspect(value)[:2] == ("WAITING_HUMAN", "PROVIDER_BUDGET_EXHAUSTED")
    assert budget_report(engine, client.budget_id)["calls_used"] == 3


def test_correcting_platform_after_log_read_requires_new_investigation(fault_agent):
    from app.api.schemas import ResumeInput, VersionedAction
    from app.domain.errors import AppError
    from app.services.human import claim, resume
    engine, provider, create, inspect, _, _ = fault_agent
    value, actor = create(customer_email="p08-wifi-none@example.test")
    advance(UUID(value["run_id"]), provider("wifi"))
    with Session(engine) as db:
        task = db.scalar(select(HumanTask).where(HumanTask.run_id == UUID(value["run_id"])))
        ticket = db.get(Ticket, UUID(value["ticket_id"]))
        claimed = claim(db, actor, task.id, VersionedAction(action_id=uuid4(), expected_version=ticket.version))
        with pytest.raises(AppError) as caught:
            resume(db, actor, task.id, ResumeInput(action_id=uuid4(), expected_version=claimed["version"], facts_patch={"platform": "ios"}))
        assert caught.value.code == "REINVESTIGATION_REQUIRED"


@pytest.mark.parametrize("point", ["after_download_log_write", "after_extract_log_window_write"])
def test_killed_fault_process_reuses_durable_artifact_and_window(fault_agent, point):
    from datetime import timedelta
    import os
    import queue
    import subprocess
    import sys
    import threading
    from sqlalchemy import update
    from app.repositories.models import ExecutionTask
    from app.workers.runtime import run_once
    engine, provider, create, inspect, _, _ = fault_agent
    client = provider()
    value, _ = create()
    run_id = UUID(value["run_id"])
    process = subprocess.Popen([sys.executable, "tests/helpers/p08_worker.py", str(run_id), str(client.budget_id)],
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
        assert not run_once(run_id, provider_session=client)
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        reader.join(timeout=2)
        process.stdout.close()
    advance(run_id, client)
    assert inspect(value)[0] == "PENDING_CONFIRMATION"
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(LogArtifact)) == 1
        assert db.scalar(select(func.count()).select_from(LogEvidence)) == 3
        for name in ("download_log", "extract_log_window"):
            assert db.scalar(select(func.count()).select_from(ToolExecution).where(ToolExecution.run_id == run_id,
                ToolExecution.tool_name == name, ToolExecution.status == "succeeded")) == 1
    # 解析、两次父编排、六次故障动作规划、一次领域分析和一次方案生成。
    assert budget_report(engine, client.budget_id)["calls_used"] == 11
