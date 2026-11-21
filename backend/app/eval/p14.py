"""固定样例对照。先执行全部检索与调查，再打开标签评分。"""
from collections import defaultdict
from datetime import datetime, timedelta
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter

from app.eval.structured import Corpus, Scope, chunk_search, claim_search
from app.providers.client import ModelClient, ModelRequest, SolutionDraft
from app.services.publications import rank_problems, scope_matches
from app.tools.mock import MockAdapter, RUNTIME_ROOT, ToolContext, load_runtime
from app.tools.registry import ToolRegistry


ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "fixtures/benchmark/p14"
ATTR_TERMS = {"spec": "连接", "policy": "连接", "connection": "连接"}


def run_route(case, strategy, limit):
    runtime = load_runtime(case["id"])
    context = ToolContext(**runtime["customer"])
    client = ModelClient()
    registry = ToolRegistry(MockAdapter(context, runtime["runtime"], client))
    trace = []
    model_calls = 0

    def call(name, **args):
        nonlocal model_calls
        if len(trace) >= limit:
            raise RuntimeError("对照超过冻结的工具次数")
        result = registry.call(name, {"customer_ref": context.customer_ref, **args}).model_dump(mode="json")
        trace.append({"tool": name, "status": result["status"], "error_code": result["error_code"], "refs": result["data_refs"]})
        model_calls += ((result.get("data") or {}).get("model_usage") or {}).get("model_calls", 0)
        return result

    needs_kb = case["requires_knowledge"]
    domains = case["domains"]
    knowledge_ok = not needs_kb
    feedback = None
    point = runtime["request"]["occurred_at"]
    if strategy in {"fixed", "all"} or needs_kb:
        result = call("search_knowledge", query=ATTR_TERMS[case["topic"]], product_ref=case["product_ref"],
                      firmware_version=case["firmware_version"])
        if needs_kb:
            knowledge_ok = result["status"] == "success"
        if strategy == "fixed":
            knowledge_ok = result["status"] == "success"
    if strategy == "all" or (strategy == "selective" and domains) or (strategy == "fixed" and not knowledge_ok):
        feedback = call("get_feedbacks", device_ref=case.get("device_ref", context.device_ref), occurred_at=point)

    domains_ok = not domains
    if strategy != "fixed" and domains and feedback and feedback["status"] == "success":
        records = feedback["data"]["records"]
        if len(records) == 1:
            downloaded = call("download_log", feedback_ref=records[0]["record_id"])
            if downloaded["status"] == "success":
                moment = datetime.fromisoformat(point)
                window = call("extract_log_window", log_ref=downloaded["data"]["log_ref"],
                              start=(moment - timedelta(minutes=2)).isoformat(), end=(moment + timedelta(minutes=2)).isoformat())
                if window["status"] == "success":
                    window_ref = window["data"]["window_ref"]
                    results = [
                        call("diagnose_wifi", window_ref=window_ref) if domain == "wifi"
                        else call("analyze_domain", window_ref=window_ref, domain=domain)
                        for domain in domains
                    ]
                    domains_ok = all(row["status"] == "success" for row in results)

    refs = list(dict.fromkeys(ref for row in trace for ref in row["refs"]))
    action = "draft" if knowledge_ok and (domains_ok or strategy == "fixed") and refs else "human"
    if action == "draft":
        _, usage = client.complete(ModelRequest(role="solution",
            input={"feedback": case["question"], "observations": trace}, allowed_evidence_refs=refs), SolutionDraft)
        model_calls += usage.model_calls
    return {"action": action, "refs": refs, "trace": trace, "tool_calls": len(trace), "model_calls": model_calls}


def timed(rows, suite, case, arm, execute):
    started = perf_counter()
    result = execute()
    rows.append({"suite": suite, "id": case["id"], "group": case["group"], "arm": arm,
                 "elapsed_ms": round((perf_counter() - started) * 1000, 3), **result})


def execute_all(inputs):
    rows = []
    corpus = Corpus.model_validate(inputs["knowledge_corpus"])
    for case in inputs["knowledge_cases"]:
        scope = Scope.model_validate(case["scope"])
        args = (corpus, scope, case["question"], inputs["knowledge_limit"])
        timed(rows, "knowledge", case, "chunks", lambda: {"refs": chunk_search(*args), "status": "retrieved"})
        timed(rows, "knowledge", case, "claims", lambda: claim_search(*args))
    for case in inputs["route_cases"]:
        for arm in ("fixed", "all", "selective"):
            timed(rows, "routing", case, arm, lambda: run_route(case, arm, inputs["route_tool_limit"]))
    memories = inputs["experience_memory"]
    probes = inputs["experience_cases"]
    assert not {row["family"] for row in memories} & {row["family"] for row in probes}
    assert max(row["recorded_at"] for row in memories) < min(row["recorded_at"] for row in probes)
    for case in probes:
        published = {row["id"]: row["question"] for row in memories
                     if row["state"] == "active" and scope_matches(row["scope"], case["scope"])}
        history = {row["id"]: row["question"] for row in memories}
        for arm, values in (("none", {}), ("history", history), ("published", published)):
            timed(rows, "experience", case, arm, lambda: {
                "refs": rank_problems(values, case["question"], inputs["experience_limit"])})
    return rows


def score(row, target):
    refs = set(row["refs"])
    if row["suite"] == "routing":
        errors = []
        if row["action"] != target["action"]:
            errors.append("wrong_next_action")
        if not set(target["required_refs"]) <= refs:
            errors.append("missing_required_evidence")
        if set(target["excluded_refs"]) & refs:
            errors.append("out_of_scope_evidence")
        if set(target["forbidden_tools"]) & {step["tool"] for step in row["trace"]}:
            errors.append("unnecessary_data_access")
        return errors
    errors = []
    wanted = set(target["refs"])
    if wanted - refs:
        errors.append("missing_required_evidence")
    if refs - wanted:
        errors.append("irrelevant_or_inapplicable_evidence")
    return errors


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["suite"], row["arm"], "全部"].append(row)
        groups[row["suite"], row["arm"], row["group"]].append(row)
    return [
        {"suite": suite, "arm": arm, "group": group, "cases": len(values),
         "passed": sum(not row["errors"] for row in values),
         "median_ms": round(median(row["elapsed_ms"] for row in values), 3),
         "tool_calls": sum(row.get("tool_calls", 0) for row in values),
         "mock_model_calls": sum(row.get("model_calls", 0) for row in values),
         "explicit_conflicts": sum(row.get("status") == "conflict" for row in values)}
        for (suite, arm, group), values in groups.items()
    ]


def main():
    raw = (DATA / "inputs.json").read_bytes()
    inputs = json.loads(raw)
    rows = execute_all(inputs)
    ratings = (DATA / "labels.json").read_bytes()
    labels = json.loads(ratings)
    assert len({(row["suite"], row["arm"], row["id"]) for row in rows}) == len(rows) == 78
    for row in rows:
        row["errors"] = score(row, labels[row["suite"]][row["id"]])
    groups = summarize(rows)
    sources = [Path(__file__), ROOT / "backend/app/eval/structured.py", ROOT / "backend/app/services/publications.py",
               ROOT / "backend/app/knowledge/text.py", ROOT / "backend/app/tools/mock.py",
               ROOT / "backend/app/tools/registry.py", ROOT / "backend/app/providers/client.py"]
    report = {"protocol_id": inputs["protocol_id"], "inputs_sha256": sha256(raw).hexdigest(),
              "labels_sha256": sha256(ratings).hexdigest(),
              "runtime_sha256": {case["id"]: sha256((RUNTIME_ROOT / f"{case['id']}.json").read_bytes()).hexdigest()
                                  for case in inputs["route_cases"]},
              "code_sha256": {source.relative_to(ROOT).as_posix(): sha256(source.read_bytes()).hexdigest()
                               for source in sources},
              "configuration": {key: value for key, value in inputs.items() if key.endswith("_limit")},
              "data_source": "mock", "external_requests": 0, "external_cost_cny": 0,
              "provider_tokens": None, "rows": rows, "groups": groups}
    out = ROOT / "output/evaluation"
    out.mkdir(parents=True, exist_ok=True)
    (out / "p14.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for group in groups:
        if group["group"] == "全部":
            print(f'{group["suite"]}/{group["arm"]}: {group["passed"]}/{group["cases"]},'
                  f' tools={group["tool_calls"]}, mock_model_calls={group["mock_model_calls"]}')
    print(f'{len(rows)} assigned runs; external_requests=0; external_cost_cny=0')


if __name__ == "__main__":
    main()
