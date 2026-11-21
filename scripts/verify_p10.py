"""串行验收一期，复用本地测试库与模拟资料。"""
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    output = root / "output/p10"
    output.mkdir(parents=True, exist_ok=True)
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    if not npm:
        raise SystemExit("请先准备项目锁定的 Node 环境")
    commands = [
        ("compose", root, ["docker", "compose", "config", "--quiet"]),
        ("backend", root, [sys.executable, "scripts/verify_backend.py", "--split"]),
        ("smoke", root, [sys.executable, "-m", "app.eval", "replay", "--suite", "smoke"]),
        *[(name, root / "frontend", [npm, "run", task]) for name, task in (
            ("api", "api:check"), ("unit", "test:unit"), ("build", "build"), ("browser", "test:e2e"))],
    ]
    results = {}
    for name, cwd, command in commands:
        with (output / f"{name}.log").open("wb") as log:
            result = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT)
        results[name] = result.returncode
        (output / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"{name}: {result.returncode}", flush=True)
        if result.returncode:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
