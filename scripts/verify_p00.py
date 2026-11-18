"""使用项目环境运行 P00 后端验收，不输出连接串。"""

import os
from pathlib import Path
import subprocess
import sys

from dotenv import load_dotenv


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", encoding="utf-8-sig")
    if not os.environ.get("AFTERSALES_TEST_DATABASE_URL"):
        raise SystemExit("缺少测试库配置，请先运行 scripts/bootstrap.ps1")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True, cwd=root)
    subprocess.run(
        [sys.executable, "-m", "pytest", "tests/unit", "tests/integration", "-v"],
        check=True, cwd=root / "backend",
    )


if __name__ == "__main__":
    main()
