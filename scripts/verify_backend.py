"""后端完整回归：只向独立测试库写入，不输出连接串。"""

import argparse
import os
from pathlib import Path
import subprocess
import sys

import psycopg
from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", action="store_true", help="每个集成测试文件使用独立进程")
    split = parser.parse_args().split
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", encoding="utf-8-sig")
    raw_url = os.environ.get("AFTERSALES_TEST_DATABASE_URL")
    if not raw_url:
        raise SystemExit("缺少测试库配置，请先运行 scripts/bootstrap.ps1")
    url = make_url(raw_url)
    if url.host not in {"localhost", "127.0.0.1"} or url.database != "aftersales_test":
        raise SystemExit("仅允许独立本机 aftersales_test")
    try:
        with psycopg.connect(raw_url, connect_timeout=4) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        raise SystemExit("测试 PostgreSQL 暂不可用，请检查 Compose 服务状态") from None
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True, cwd=root)
    backend = root / "backend"
    if split:
        integration = sorted((backend / "tests/integration").glob("test_*.py"))
        groups = [("tests/unit",), *((str(path.relative_to(backend)),) for path in integration)]
    else:
        groups = [("tests/unit", "tests/integration")]
    for targets in groups:
        subprocess.run(
            [sys.executable, "-m", "pytest", *targets, "-v", "--tb=short", "--maxfail=1"],
            check=True, cwd=backend,
        )


if __name__ == "__main__":
    main()
