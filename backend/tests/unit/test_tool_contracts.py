"""工具、模型和公开样例的数据边界。"""

import asyncio
import json
from pathlib import Path

import pytest

from app.eval.replay import evaluate_case, replay_case
from app.providers.client import ModelClient, ModelFailure, ModelProfile, ModelRequest, SolutionDraft
from app.tools.mock import MockAdapter, SCENARIO_IDS, ToolContext, load_runtime
from app.tools.redaction import redact
from app.tools.registry import ToolRegistry, tool_schemas


def registry(scenario_id="S03"):
    fixture = load_runtime(scenario_id)
    return ToolRegistry(MockAdapter(ToolContext(**fixture["customer"]), fixture["runtime"]))


def bound(**extra):
    return {"customer_ref": "customer-demo-01", **extra}


def window(tools):
    downloaded = tools.call("download_log", bound(feedback_ref="feedback:S03:a"))
    assert downloaded.status == "success"
    extracted = tools.call("extract_log_window", bound(log_ref=downloaded.data.log_ref,
        start="2026-11-18T09:58:00+08:00", end="2026-11-18T10:02:00+08:00"))
    assert extracted.status == "success"
    return extracted


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_twelve_seeds_replay_without_opening_evaluation_labels(monkeypatch, scenario_id):
    read_text = Path.read_text

    def guarded(path, *args, **kwargs):
        assert "evaluation" not in path.parts, "运行路径不得读取隐藏标签"
        return read_text(path, *args, **kwargs)

    with monkeypatch.context() as scope:
        scope.setattr(Path, "read_text", guarded)
        actual = replay_case(scenario_id)
    assert evaluate_case(actual) == []
    assert "EVAL_PRIVATE_" not in json.dumps(actual)


def test_six_tools_publish_closed_input_and_output_schemas():
    schemas = tool_schemas()
    assert set(schemas) == {"search_knowledge", "get_feedbacks", "download_log", "extract_log_window", "diagnose_wifi", "analyze_domain"}
    for value in schemas.values():
        assert value["input"]["additionalProperties"] is False
        assert value["output"]["additionalProperties"] is False


@pytest.mark.parametrize("tool,args,code", [
    ("exec_shell", {}, "TOOL_NOT_ALLOWED"),
    ("get_feedbacks", bound(customer_email="other@example.test"), "INVALID_ARGUMENTS"),
    ("get_feedbacks", bound(customer_ref="customer-other"), "FORBIDDEN"),
    ("get_feedbacks", bound(device_ref="DEVICE-B"), "FORBIDDEN"),
    ("get_feedbacks", bound(window_minutes="30"), "INVALID_ARGUMENTS"),
    ("get_feedbacks", bound(window_minutes=True), "INVALID_ARGUMENTS"),
    ("get_feedbacks", bound(occurred_at="2026-11-18T10:00:00"), "INVALID_ARGUMENTS"),
    ("download_log", bound(feedback_ref="../evaluation/S01.json"), "INVALID_ARGUMENTS"),
    ("download_log", bound(feedback_ref="feedback:S03:a", path="C:/secret"), "INVALID_ARGUMENTS"),
    ("download_log", bound(feedback_ref="https://internal.example/log"), "INVALID_ARGUMENTS"),
    ("extract_log_window", bound(log_ref="log:S03:a", start="2026-11-19T00:00:00Z", end="2026-11-18T00:00:00Z"), "INVALID_ARGUMENTS"),
    ("extract_log_window", bound(log_ref="log:S03:a", start="2026-11-18T00:00:00Z", end="2026-11-20T00:00:00Z"), "INVALID_ARGUMENTS"),
    ("analyze_domain", bound(window_ref="window:unknown", domain="ota"), "FORBIDDEN"),
])
def test_unauthorized_or_malformed_parameters_never_return_data(tool, args, code):
    result = registry().call(tool, args)
    assert result.status == "error" and result.error_code == code
    assert result.data is None and result.data_refs == []
    assert "other@example.test" not in result.model_dump_json()


@pytest.mark.parametrize("code,retryable", [
    ("AUTH_FAILED", False), ("RATE_LIMITED", True), ("TIMEOUT", True),
    ("DOWNLOAD_FAILED", False), ("PARSE_FAILED", False),
])
def test_tool_failure_codes_are_explicit_and_not_empty_success(code, retryable):
    tools = registry()
    tools.adapter.runtime["tool_errors"] = {"get_feedbacks": code}
    result = tools.call("get_feedbacks", bound(device_ref="DEVICE-A"))
    assert result.status == "error" and result.error_code == code
    assert result.retryable is retryable and result.data is None


def test_feedback_is_filtered_by_device_platform_then_time_and_never_latest():
    tools = registry("S09")
    result = tools.call("get_feedbacks", bound(device_ref="DEVICE-A", platform="android", occurred_at="2026-11-18T10:00:00+08:00"))
    assert result.status == "needs_human" and result.data.requires_selection
    assert result.data_refs == ["feedback:S09:a1", "feedback:S09:a2"]
    none = tools.call("get_feedbacks", bound(device_ref="DEVICE-A", platform="ios", occurred_at="2026-11-18T10:00:00+08:00"))
    assert none.status == "no_data" and none.error_code == "NO_MATCHING_RECORD"
    outside = tools.call("get_feedbacks", bound(device_ref="DEVICE-A", occurred_at="2026-11-19T10:00:00+08:00"))
    assert outside.error_code == "NO_MATCHING_RECORD"
    empty = registry("S01").call("get_feedbacks", bound(device_ref="DEVICE-A"))
    assert empty.error_code == "NO_FEEDBACK"
    missing = tools.call("get_feedbacks", bound())
    assert missing.status == "needs_human" and missing.data.missing_fields == ["device_ref", "occurred_at"]
    assert tools.call("download_log", bound(feedback_ref="feedback:S09:foreign")).error_code == "FORBIDDEN"


def test_attachments_download_parse_window_and_session_ownership_are_distinct():
    tools = registry()
    # 没有授权下载的日志句柄不可直接读取。
    assert tools.call("extract_log_window", bound(log_ref="log:S03:a", start="2026-11-18T09:58:00Z",
                                                  end="2026-11-18T10:02:00Z")).error_code == "FORBIDDEN"
    result = window(tools)
    serialized = result.model_dump_json()
    assert "MOCK_SECRET_MUST_NOT_LEAK" not in serialized and "[REDACTED]" in serialized
    assert result.source.record_ids == result.data_refs
    assert result.source.data_source == result.data_source == "mock" and result.fetched_at.tzinfo
    assert registry().call("diagnose_wifi", bound(window_ref=result.data.window_ref)).error_code == "FORBIDDEN"
    empty = tools.call("extract_log_window", bound(log_ref="log:S03:a", start="2026-11-19T09:58:00Z", end="2026-11-19T10:02:00Z"))
    assert empty.status == "no_data" and empty.error_code == "NO_MATCHING_RECORD"
    assert empty.data.missing_fields == ["matching_log_window"] and empty.data.viewed_range
    assert registry("S06").call("download_log", bound(feedback_ref="feedback:S06:a")).error_code == "NO_ATTACHMENT"
    tools.adapter.runtime["logs"].clear()
    assert tools.call("download_log", bound(feedback_ref="feedback:S03:a")).error_code == "DOWNLOAD_FAILED"


def test_corrupt_log_is_parse_failure_and_rule_vs_model_analysis_stays_marked():
    tools = registry()
    value = window(tools)
    args = bound(window_ref=value.data.window_ref)
    rule = tools.call("diagnose_wifi", args)
    model = tools.call("analyze_domain", {**args, "domain": "ota"})
    assert rule.data.analysis_mode == "rule" and rule.data.model_usage is None
    assert model.data.analysis_mode == "model" and model.data.model_usage["simulated"] is True
    assert model.data.model_usage["cost"] is None
    assert tools.call("analyze_domain", {**args, "domain": "brakes"}).error_code == "UNSUPPORTED_DOMAIN"
    tools.adapter.runtime["logs"]["log:S03:a"] = "not a parsed log"
    broken = tools.call("extract_log_window", bound(log_ref="log:S03:a", start="2026-11-18T09:58:00Z", end="2026-11-18T10:02:00Z"))
    assert broken.error_code == "PARSE_FAILED"


def test_unexpected_adapter_exception_does_not_echo_private_exception(monkeypatch):
    tools = registry()

    def failed(*args):
        raise RuntimeError("private@example.test password=unsafe")

    monkeypatch.setattr(tools.adapter, "dispatch", failed)
    result = tools.call("get_feedbacks", bound(device_ref="DEVICE-A"))
    assert result.error_code == "TOOL_FAILED"
    assert "unsafe" not in result.model_dump_json() and "private@example.test" not in result.model_dump_json()


def test_invalid_tool_output_is_distinct_from_invalid_input(monkeypatch):
    tools = registry()
    monkeypatch.setattr(tools.adapter, "dispatch", lambda *_: ({"unexpected": "private data"}, [], "success"))
    result = tools.call("get_feedbacks", bound(device_ref="DEVICE-A"))
    assert result.status == "error" and result.error_code == "PARSE_FAILED"
    assert result.data is None and "private data" not in result.model_dump_json()


def test_sensitive_search_text_is_not_echoed_in_source_query():
    result = registry("S01").call("search_knowledge", bound(query="password=hidden user@example.test", product_ref="PILOT-01"))
    assert "hidden" not in result.model_dump_json() and "user@example.test" not in result.model_dump_json()


def request():
    return ModelRequest(role="solution", input={"feedback_text": "模拟咨询"}, allowed_evidence_refs=["kb:test"])


@pytest.mark.parametrize("raw,code", [
    ("not JSON", "INVALID_MODEL_OUTPUT"),
    ('{"reply_draft":"missing fields"}', "INVALID_MODEL_OUTPUT"),
    (json.dumps({"internal_plan": "mock", "reply_draft": "mock", "data_source": "real", "evidence_refs": []}), "UNTRUSTED_MODEL_EVIDENCE"),
    (json.dumps({"internal_plan": "mock", "reply_draft": "mock", "data_source": "mock", "evidence_refs": ["other:customer"]}), "UNTRUSTED_MODEL_EVIDENCE"),
    (json.dumps({"internal_plan": "mock", "reply_draft": "mock", "data_source": "mock", "evidence_refs": [], "customer_email": "other@example.test"}), "INVALID_MODEL_OUTPUT"),
])
def test_model_json_schema_and_evidence_are_checked(raw, code):
    async def transport(_):
        return raw

    with pytest.raises(ModelFailure) as exc:
        ModelClient(transport=transport).complete(request(), SolutionDraft)
    assert exc.value.code == code


def test_model_timeout_is_enforced_and_never_falls_back():
    async def transport(_):
        await asyncio.sleep(1)
        raise AssertionError("不能执行到这里")

    client = ModelClient({"solution": ModelProfile(timeout_seconds=0.005)}, transport)
    with pytest.raises(ModelFailure, match="MODEL_TIMEOUT"):
        client.complete(request(), SolutionDraft)
    with pytest.raises(ModelFailure, match="PROVIDER_NOT_CONFIGURED"):
        ModelClient({"solution": ModelProfile(provider="unconfigured-real-provider")}).complete(request(), SolutionDraft)
    with pytest.raises(ModelFailure, match="PROVIDER_NOT_CONFIGURED"):
        ModelClient().complete(request().model_copy(update={"data_source": "real"}), SolutionDraft)


def test_runtime_loader_cannot_be_used_to_read_labels_or_arbitrary_paths():
    for value in ("../evaluation/S01", "S01.json", "C:/secret", "S13"):
        with pytest.raises(ValueError):
            load_runtime(value)


def test_redaction_covers_headers_json_credentials_and_email():
    value = redact('Authorization: Bearer hidden\nCookie: a=hidden\n{"password":"hidden", "token": "hidden"}\nuser@example.test')
    assert "hidden" not in value and "user@example.test" not in value


def test_mock_usage_has_no_invented_tokens_or_cost():
    result, usage = ModelClient().complete(request(), SolutionDraft)
    assert result.data_source == "mock" and result.reviewed is False
    assert usage.model_calls == 1 and usage.simulated
    assert usage.provider == "mock" and usage.model == "deterministic-v1" and usage.role == "solution"
    assert usage.input_tokens is usage.output_tokens is usage.cost is None
