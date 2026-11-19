import json
from pathlib import Path

from app.providers.client import ModelClient, ModelRequest, SolutionDraft
from app.tools.mock import MockAdapter, ToolContext, load_runtime
from app.tools.registry import ToolRegistry


EVALUATION_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "evaluation"


def replay_case(scenario_id: str) -> dict:
    """只用公开脚本和当前工具结果回放，不读取答案；不是 Agent 的决策评测。"""
    fixture = load_runtime(scenario_id)
    client = ModelClient()
    registry = ToolRegistry(MockAdapter(ToolContext(**fixture["customer"]), fixture["runtime"], client))
    handles, trace, refs = {}, [], []
    for step in fixture["steps"]:
        arguments = {key: handles.get(value, value) if isinstance(value, str) else value
                     for key, value in step["arguments"].items()}
        result = registry.call(step["tool"], arguments)
        value = result.model_dump(mode="json")
        trace.append({"tool": step["tool"], "result": value})
        refs.extend(value["data_refs"])
        if step["tool"] == "download_log" and result.status == "success":
            handles["$last_log"] = value["data"]["log_ref"]
        if step["tool"] == "extract_log_window" and result.status == "success":
            handles["$last_window"] = value["data"]["window_ref"]
    # 明确缺口/冲突/失败时不生成看似完成的方案，不模拟后续阶段的自动调查。
    outcome = "human_review" if any(row["result"]["status"] != "success" for row in trace) else "mock_draft"
    model_request, draft, usage = None, None, None
    if outcome == "mock_draft":
        request = ModelRequest(role="solution", input={"request": fixture["request"], "tool_results": trace},
                               allowed_evidence_refs=list(dict.fromkeys(refs)))
        model_request = request.model_dump(mode="json")
        result, measured = client.complete(request, SolutionDraft)
        draft, usage = result.model_dump(mode="json"), measured.model_dump()
    return {"scenario_id": scenario_id, "trace": trace, "model_request": model_request,
            "draft": draft, "usage": usage, "outcome": outcome, "data_source": "mock"}


def evaluate_case(actual: dict) -> list[str]:
    """回放结束后才读取独立标签；失败信息不包含标签原文。"""
    scenario_id = actual["scenario_id"]
    # 复用公开编号白名单，不允许调用方把文件路径当作编号。
    from app.tools.mock import SCENARIO_IDS
    if scenario_id not in SCENARIO_IDS:
        raise ValueError("未知场景")
    expected = json.loads((EVALUATION_ROOT / f"{scenario_id}.json").read_text(encoding="utf-8"))
    errors = []
    results = [row["result"] for row in actual["trace"]]
    if [row["status"] for row in results] != expected["expected_statuses"]:
        errors.append("tool_status")
    if [row["error_code"] for row in results] != expected["expected_error_codes"]:
        errors.append("tool_error_code")
    refs = {ref for row in results for ref in row["data_refs"]}
    if not set(expected["required_refs"]) <= refs or set(expected["excluded_refs"]) & refs:
        errors.append("evidence_scope")
    if set(expected["must_not_call"]) & {row["tool"] for row in actual["trace"]}:
        errors.append("tool_scope")
    if actual["outcome"] != expected["acceptable_next_step"]:
        errors.append("next_step")
    serialized = json.dumps(actual, ensure_ascii=False)
    if any(value in serialized for value in [expected["hidden_canary"], "MOCK_SECRET_MUST_NOT_LEAK", *expected["forbidden_conclusions"]]):
        errors.append("context_isolation")
    return errors
