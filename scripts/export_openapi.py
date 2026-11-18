"""本地导出公开契约供前端生成类型；不需要服务或数据库连接。"""

import json
import argparse
from pathlib import Path

from app.main import app


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()
    value = json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n"
    if args.stdout:
        print(value, end="")
        raise SystemExit(0)
    target = Path(__file__).resolve().parents[1] / "frontend" / "openapi.json"
    target.write_text(value, encoding="utf-8")
    print("OpenAPI 已导出。")
