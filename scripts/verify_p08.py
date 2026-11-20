"""P08公开样例/HTTP契约验收；不调用模型网络或企业后台。"""

import json
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", encoding="utf-8-sig")
    output = root / "output/p08"
    output.mkdir(parents=True, exist_ok=True)
    junit = output / "contract-tests.xml"
    result = subprocess.run([sys.executable, "-m", "pytest", "tests/unit/test_fault_logs.py",
        "tests/integration/test_p08.py", "-q", "--tb=short", "--maxfail=1", f"--junitxml={junit}"], cwd=root / "backend")
    suites = ElementTree.parse(junit).getroot().findall("testsuite") if junit.exists() else []
    report = {"suite": "p08", "data_source": "mock", "inference_mode": "contract", "real_acceptance": False,
              "passed": result.returncode == 0, "tests": sum(int(row.get("tests", 0)) for row in suites),
              "failures": sum(int(row.get("failures", 0)) + int(row.get("errors", 0)) for row in suites),
              "exit_code": result.returncode, "limitations": "仅验证工程契约，不代表模型诊断准确率或生产接口验收。"}
    (output / "contract-summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
