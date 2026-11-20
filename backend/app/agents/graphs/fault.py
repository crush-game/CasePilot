"""P08 故障子图：模型选择受控动作，程序落实日志优先、归属及领域覆盖。"""

import time

from langgraph.graph import END, START, StateGraph

from app.faults.contracts import FaultAnalysis, FaultDecision, FaultResult
from app.providers.client import ModelFailure
from app.providers.ledger import ProviderFailure
from app.services.tickets import digest


PLAN = "你是受控故障调查员。只从allowed_actions选动作；有详细日志先下载并查看时间窗，不能由FAQ或埋点替代。WiFi与OTA分开分析，不能凭升级和断连的时间先后确认因果；证据不足选human，完整观察才finish。多条反馈由人工选，不能挑最新；不输出思维链。"
ANALYZE = "分析指定领域的脱敏日志，仅引用该领域原文。区分观察、支持/反对证据和候选解释；candidate_causes必须unconfirmed并列出required_verification。时间相邻不是升级导致断连的证明；没有该领域日志不能用WiFi记录替代OTA证据。保留查看时间窗与局限，不输出思维链或已解决结论。"


def build_fault_graph(state_schema, io):
    ctx = io.ctx

    def wrap(name, function, following, *, terminal=False):
        def run(state):
            started = time.monotonic()
            try:
                if not terminal:
                    io.guard(state)
                result = function(state)
            except (ModelFailure, ProviderFailure) as exc:
                usage = getattr(exc, "usage", None)
                result = {"fault_error": exc.code, "fault_next": "finish", "_usage":
                          usage.model_dump(mode="json") if hasattr(usage, "model_dump") else usage or {"model_calls": 0}}
            ctx.control(state, allow_pause=True)
            usage = result.pop("_usage", {"model_calls": 0})
            steps = state.get("completed_steps", [])
            result["completed_steps"] = [*steps, {"logical_step_id": f"{ctx.epoch}:fault.{name}:{len(steps)}",
                "node_name": "fault." + name, "epoch": ctx.epoch, "case_version": state["case_version"],
                "status": "failed" if result.get("fault_error") else "succeeded", "usage": usage,
                "duration_ms": int((time.monotonic() - started) * 1000), "output_refs": {
                    key: result[key] for key in ("fault_task", "fault_observation", "fault_decision", "fault_report", "fault_error", "fault_next") if key in result}}]
            result.setdefault("fault_next", following)
            return result
        return run

    def begin(state):
        missing = [key for key in ("device_ref", "occurred_at", "platform", "firmware_version", "product_ref") if not state["request"].get(key)]
        return {"fault_candidates": [], "fault_selected_feedback": None, "fault_artifact": None, "fault_no_attachment": False,
            "fault_window_refs": [], "fault_viewed_range": {}, "fault_source_kind": "none", "fault_domain_reports": {},
            "fault_actions": [], "fault_action_history": [], "fault_expanded": False, "fault_window_read": False,
            "fault_coverage_complete": True, "fault_error": "MISSING_FACTS" if missing else None,
            "missing_fields": missing, **({"fault_next": "finish"} if missing else {})}

    def allowed(state):
        actions = ["human"]
        if not state.get("fault_candidates"):
            return [*actions, "get_feedbacks"]
        if not state.get("fault_artifact"):
            return [*actions, "get_wifi_telemetry" if state["fault_no_attachment"] else "download_log"]
        if not state["fault_window_read"]:
            return [*actions, "extract_log_window"]
        covered = set(state["fault_domain_reports"])
        required = set(state["fault_task"]["domains"])
        if required <= covered:
            return [*actions, "finish"]
        if "wifi" in required - covered:
            actions.append("diagnose_wifi")
        actions.append("analyze_domain")
        if not state["fault_expanded"] and state["fault_source_kind"] == "detailed_log":
            actions.append("expand_window")
        return actions

    def plan(state):
        refs = state.get("fault_window_refs", [])
        evidence = io.citations(state, refs)
        choices = allowed(state)
        row = io.model(state, "fault.plan", FaultDecision, PLAN, {"original_question": state["request"]["feedback_text"],
            "task": state["fault_task"], "confirmed_scope": {key: state["request"].get(key) for key in (
                "device_ref", "product_ref", "firmware_version", "app_version", "platform", "occurred_at")},
            "allowed_actions": choices, "candidates": state["fault_candidates"], "artifact": state["fault_artifact"],
            "no_attachment_confirmed": state["fault_no_attachment"], "viewed_range": state["fault_viewed_range"],
            "domain_reports": state["fault_domain_reports"], "evidence": evidence}, refs)
        decision = row["value"]
        action = decision["action"]
        if action not in choices:
            raise ProviderFailure("FAULT_ACTION_NOT_ALLOWED")
        signature = digest({"action": action, "domain": decision["domain"], "artifact": state["fault_artifact"],
                            "refs": refs, "expanded": state["fault_expanded"], "covered_domains": sorted(state["fault_domain_reports"])})
        if signature in state["fault_action_history"]:
            raise ProviderFailure("NO_PROGRESS")
        if action == "human":
            return {"fault_decision": decision, "fault_error": "FAULT_MODEL_REQUESTED_HUMAN", "fault_next": "finish", "_usage": row["usage"]}
        return {"fault_decision": decision, "fault_action_history": [*state["fault_action_history"], signature],
                "fault_next": "finish" if action == "finish" else "analyze" if action == "analyze_domain" else "execute", "_usage": row["usage"]}

    def execute(state):
        action = state["fault_decision"]["action"]
        args = {}
        name = action
        if action in {"download_log", "get_wifi_telemetry"}:
            if action == "get_wifi_telemetry" and (not state["fault_no_attachment"] or state["fault_task"]["domains"] != ["wifi"]):
                raise ProviderFailure("NO_DETAILED_LOG")
            args["feedback_ref"] = state["fault_selected_feedback"]
        if action in {"extract_log_window", "expand_window"}:
            name = "extract_log_window"
            args = {"artifact_ref": state["fault_artifact"]["artifact_ref"],
                    "window_kind": "expanded" if action == "expand_window" else "initial"}
        row = io.fault_tool(state, name, args)
        observation = row["value"]
        result = {"fault_observation": observation, "fault_actions": [*state["fault_actions"], row["action_id"]], "_usage": row["usage"]}
        code, data = observation["error_code"], observation["data"]
        if observation["status"] == "error":
            return {**result, "fault_error": code, "fault_next": "finish"}
        if action == "get_feedbacks":
            records = data.get("records", [])
            result["fault_candidates"] = records
            if code:
                result.update(fault_error=code, missing_fields=data.get("missing_fields", []), fault_next="finish")
            else:
                selected = state.get("selected_feedback_ref")
                if selected and selected not in {item["record_id"] for item in records}:
                    result.update(fault_error="FEEDBACK_SCOPE_MISMATCH", fault_next="finish")
                elif len(records) > 1 and not selected:
                    result.update(fault_error="FEEDBACK_SELECTION_REQUIRED", fault_next="finish")
                else:
                    result["fault_selected_feedback"] = selected or records[0]["record_id"]
        elif action == "download_log" and code == "NO_ATTACHMENT":
            result["fault_no_attachment"] = True
            if state["fault_task"]["domains"] != ["wifi"]:
                result.update(fault_error="NO_DETAILED_LOG", fault_next="finish")
        elif action in {"download_log", "get_wifi_telemetry"}:
            if code:
                result.update(fault_error=code, fault_next="finish")
            else:
                result.update(fault_artifact=data, fault_source_kind=data["source_kind"])
        elif action in {"extract_log_window", "expand_window"}:
            result.update(fault_window_refs=observation["data_refs"], fault_viewed_range=data["viewed_range"],
                fault_window_read=True, fault_expanded=action == "expand_window", fault_coverage_complete=data["coverage_complete"])
            if not data["coverage_complete"]:
                result.update(fault_error="EVIDENCE_WINDOW_TRUNCATED", fault_next="finish")
            elif code and (action == "expand_window" or state["fault_source_kind"] == "telemetry"):
                result.update(fault_error="NO_MATCHING_LOG_WINDOW", fault_next="finish")
            if action == "expand_window":
                result["fault_domain_reports"] = {}
        elif action == "diagnose_wifi":
            if "wifi" not in state["fault_task"]["domains"]:
                raise ProviderFailure("UNSUPPORTED_DOMAIN")
            if code:
                result.update(fault_error="INSUFFICIENT_DOMAIN_EVIDENCE", fault_next="finish")
            else:
                result["fault_domain_reports"] = {**state["fault_domain_reports"], "wifi": {**data, "evidence_refs": observation["data_refs"]}}
        return result

    def analyze(state):
        domain = state["fault_decision"]["domain"]
        if domain not in state["fault_task"]["domains"]:
            raise ProviderFailure("UNSUPPORTED_DOMAIN")
        evidence = [row for row in io.citations(state, state["fault_window_refs"]) if row["domain"] == domain]
        if not evidence:
            raise ProviderFailure("INSUFFICIENT_DOMAIN_EVIDENCE")
        refs = [row["ref"] for row in evidence]
        row = io.model(state, "fault.domain." + domain, FaultAnalysis, ANALYZE,
            {"domain": domain, "original_question": state["request"]["feedback_text"],
             "viewed_range": state["fault_viewed_range"], "source_kind": state["fault_source_kind"], "evidence": evidence}, refs)
        value = row["value"]
        nested = [ref for finding in value["findings"] for ref in finding["evidence_refs"]]
        nested += [ref for cause in value["candidate_causes"] for ref in [*cause["supporting_refs"], *cause["contradicting_refs"]]]
        if value["domain"] != domain or not set(nested) <= set(refs):
            raise ProviderFailure("UNTRUSTED_MODEL_EVIDENCE")
        return {"fault_domain_reports": {**state["fault_domain_reports"], domain: {**value, "analysis_mode": "model"}}, "_usage": row["usage"]}

    def finish(state):
        reports = state.get("fault_domain_reports", {})
        complete = set(state["fault_task"]["domains"]) <= set(reports)
        code = state.get("fault_error") or ("TELEMETRY_ONLY" if state["fault_source_kind"] == "telemetry" else None)
        if not complete and not code:
            code = "INSUFFICIENT_DOMAIN_EVIDENCE"
        findings = [value for report in reports.values() for value in report["findings"]]
        refs = list(dict.fromkeys(ref for report in reports.values() for ref in report["evidence_refs"]))
        refs += [ref for item in findings for ref in item["evidence_refs"]]
        for report in reports.values():
            for cause in report["candidate_causes"]:
                refs.extend([*cause["supporting_refs"], *cause["contradicting_refs"]])
        refs = list(dict.fromkeys(refs))
        limitations = list(dict.fromkeys(["只覆盖已查看范围；时间相邻不证明因果，候选原因仍需验证。",
            *[text for report in reports.values() for text in report["limitations"]]]))
        report = FaultResult(status="completed" if not code else "needs_human", findings=findings, evidence_refs=refs,
            unresolved_items=[code] if code else [], stop_reason=code or "FAULT_INVESTIGATION_COMPLETE",
            source_actions=state.get("fault_actions", []), inspected_domains=list(reports),
            candidate_causes=[value for item in reports.values() for value in item["candidate_causes"]], limitations=limitations,
            viewed_range=state.get("fault_viewed_range", {}), source_kind=state.get("fault_source_kind", "none")).model_dump(mode="json")
        return {"fault_report": report, "fault_history": [*state.get("fault_history", []), {"task": state["fault_task"], "result": report}],
            "evidence_refs": list(dict.fromkeys([*state.get("evidence_refs", []), *refs, *state.get("fault_window_refs", [])])),
            "stop_reason": code, "next_action": "human_interrupt" if code else "supervisor", "fault_next": END}

    builder = StateGraph(state_schema)
    nodes = {"begin": (begin, "plan"), "plan": (plan, "execute"), "execute": (execute, "plan"),
             "analyze": (analyze, "plan"), "finish": (finish, END)}
    for name, (function, following) in nodes.items():
        builder.add_node(name, wrap(name, function, following, terminal=name == "finish"))
        builder.add_conditional_edges(name, lambda state: state["fault_next"], {key: key for key in [*nodes, END]})
    builder.add_edge(START, "begin")
    return builder.compile()
