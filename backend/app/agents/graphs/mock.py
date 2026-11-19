"""P02 固定 Mock 工作流；路由由规则决定，不代表真实 Agent 决策。"""

import time
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.providers.client import ModelFailure


GRAPH_VERSION = "mock-v1"


class CaseState(TypedDict, total=False):
    ticket_id: str
    run_id: str
    case_version: int
    request: dict
    ticket_metadata: dict
    data_source: str
    evidence_refs: list[str]
    completed_steps: list[dict]
    consumed_action_ids: list[str]
    budget_epoch: int
    missing_fields: list[str]
    next_action: str
    stop_reason: str | None
    solution: dict
    complete: bool
    model_usage: dict


def build_graph(saver, ctx):
    def parse_request(state):
        return {}

    def supervisor(state):
        missing = [name for name in ("device_ref", "occurred_at") if not state["request"].get(name)]
        return {"missing_fields": missing, "stop_reason": "MISSING_FACTS" if missing else None,
                "next_action": "human_interrupt" if missing else "knowledge_investigation"}

    def human_interrupt(state):
        response = interrupt({"reason_code": state.get("stop_reason") or "MANUAL_REVIEW",
                              "missing_fields": state.get("missing_fields", []), "data_source": "mock"})
        action_id = response["action_id"]
        consumed = state.get("consumed_action_ids", [])
        if action_id in consumed:
            raise RuntimeError("人工动作已消费，不能提交到另一个暂停点")
        return {"request": {**state["request"], **response["facts_patch"]},
                "consumed_action_ids": [*consumed, action_id], "budget_epoch": response["budget_epoch"],
                "case_version": response["case_version"], "stop_reason": None}

    def investigate(name):
        def node(state):
            logical_step = f"{name}:{len(state.get('completed_steps', []))}"
            result = ctx.tool(name, state, logical_step)
            if result["status"] != "success":
                return {"stop_reason": "MOCK_TOOL_ERROR", "next_action": "human_interrupt"}
            refs = list(dict.fromkeys([*state.get("evidence_refs", []), *result["evidence_refs"]]))
            return {"evidence_refs": refs}
        return node

    def generate_solution(state):
        try:
            solution, usage = ctx.model(state)
        except ModelFailure as exc:
            return {"stop_reason": exc.code, "next_action": "human_interrupt"}
        return {"solution": solution, "model_usage": usage}

    def validate_solution(state):
        if state["solution"]["data_source"] != "mock":
            raise RuntimeError("P02 仅允许 Mock 方案")
        return {}

    def finalize_run(state):
        return {"complete": True}

    def wrap(name, node, next_action):
        def run(state):
            reason = ctx.control(state, allow_pause=name == "human_interrupt")
            if reason:
                return {"stop_reason": reason, "next_action": "human_interrupt"}
            started = time.monotonic()
            result = node(state)
            # 在检查点写入前再次检验执行权，失权的迟到结果不得继续投影。
            ctx.control(state, allow_pause=True)
            epoch = result.get("budget_epoch", state.get("budget_epoch", 0))
            steps = state.get("completed_steps", [])
            result["completed_steps"] = [*steps, {
                "logical_step_id": f"{epoch}:{name}:{len(steps)}", "node_name": name, "epoch": epoch,
                "case_version": result.get("case_version", state["case_version"]),
                "duration_ms": int((time.monotonic() - started) * 1000), "status": "succeeded",
                "usage": result.get("model_usage", {"model_calls": 0}),
            }]
            result.setdefault("next_action", next_action)
            return result
        return run

    nodes = {
        "parse_request": (parse_request, "supervisor"),
        "supervisor": (supervisor, "knowledge_investigation"),
        "knowledge_investigation": (investigate("mock_knowledge"), "fault_investigation"),
        "fault_investigation": (investigate("mock_fault"), "generate_solution"),
        "generate_solution": (generate_solution, "validate_solution"),
        "validate_solution": (validate_solution, "finalize_run"),
        "human_interrupt": (human_interrupt, "supervisor"),
        "finalize_run": (finalize_run, END),
    }
    builder = StateGraph(CaseState)
    for name, (node, following) in nodes.items():
        builder.add_node(name, wrap(name, node, following))
        builder.add_conditional_edges(name, lambda state: state["next_action"], {target: target for target in [*nodes, END]})
    builder.add_edge(START, "parse_request")
    return builder.compile(checkpointer=saver)
