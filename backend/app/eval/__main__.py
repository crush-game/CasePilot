import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from app.eval.replay import evaluate_case, replay_case
from app.tools.mock import SCENARIO_IDS


ENGINEERING_CHECKS = {
    "S11": [
        "test_mock_create_pause_claim_resume_solution_review_contact_close",
        "test_consumed_resume_is_not_sent_again_at_next_interrupt",
        "test_takeover_rejects_late_projection_and_waits_for_lock_release",
    ],
    "S12": [
        "test_worker_can_wait_for_future_task_availability",
        "test_force_kill_before_projection_recovers_to_one_human_task",
        "test_force_kill_after_tool_result_reuses_cached_logical_action",
        "test_force_kill_after_graph_completion_projects_saved_solution",
        "test_step_budget_and_cross_epoch_limit_end_in_human",
        "test_expired_lease_cannot_bypass_live_run_lock",
    ],
}


def main():
    parser = argparse.ArgumentParser(description="P04 确定性契约回放，不报告真实模型或根因效果")
    parser.add_argument("command", choices=["replay", "live"])
    parser.add_argument("--suite", choices=["smoke", "p06"], required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / ".env", encoding="utf-8-sig")
    if args.command == "live" and args.suite == "p06":
        from app.eval.live import main as live_main
        try:
            return live_main()
        except Exception:
            print(json.dumps({"passed": False, "real_acceptance": False, "error_code": "LIVE_CONFIGURATION_OR_STORAGE_ERROR"}))
            return 2
    if args.command != "replay" or args.suite != "smoke":
        parser.error("使用 replay --suite smoke 或 live --suite p06")
    # S11/S12 的恢复验收必须用真实本机测试库，不能把纯模拟调用当成崩溃恢复通过。
    raw_url = os.environ.get("AFTERSALES_TEST_DATABASE_URL")
    if not raw_url:
        raise SystemExit("smoke 包含数据库恢复检查，必须配置独立测试库。")
    url = make_url(raw_url)
    if url.database != "aftersales_test" or url.host not in {"localhost", "127.0.0.1"}:
        raise SystemExit("仅允许本机 aftersales_test；未运行回放。")
    cases, passed = [], True
    for scenario_id in SCENARIO_IDS:
        actual = replay_case(scenario_id)
        errors = evaluate_case(actual)
        cases.append({"scenario_id": scenario_id, "passed": not errors, "errors": errors, "actual": actual})
        passed = passed and not errors
        print(f"{scenario_id}: {'PASS' if not errors else 'FAIL'} (mock contract)", flush=True)
    engineering = []
    for scenario_id, checks in ENGINEERING_CHECKS.items():
        targets = [f"tests/integration/test_p02.py::{name}" for name in checks]
        result = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=short", *targets],
                                cwd=root / "backend", timeout=240, check=False)
        engineering.append({"scenario_id": scenario_id, "passed": result.returncode == 0, "checks": checks})
        passed = passed and result.returncode == 0
    output = root / "output" / "evaluation"
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{args.suite}.json").write_text(json.dumps({"data_source": "mock", "suite": args.suite,
        "passed": passed, "cases": cases, "engineering": engineering}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"smoke: {'PASS' if passed else 'FAIL'}; 12 seed contracts + PostgreSQL/process recovery checks")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
