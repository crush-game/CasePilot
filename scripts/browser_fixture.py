"""P03 浏览器验收专用：只操作本机独立测试库，凭据仅供父测试进程读取。"""

import argparse
import json
import os
from pathlib import Path
import secrets
from uuid import UUID, uuid4

from dotenv import load_dotenv
from sqlalchemy.engine import make_url


def main():
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env", encoding="utf-8-sig")
    raw_url = os.environ["AFTERSALES_TEST_DATABASE_URL"]
    url = make_url(raw_url)
    if url.database != "aftersales_test" or url.host not in {"127.0.0.1", "localhost"}:
        raise SystemExit("浏览器验收只允许本机 aftersales_test")
    os.environ["AFTERSALES_DATABASE_URL"] = raw_url
    os.environ["AFTERSALES_ALLOWED_ORIGINS"] = json.dumps(["http://127.0.0.1:15173"])
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "api", "worker"])
    parser.add_argument("--run-id", type=UUID)
    args = parser.parse_args()

    from sqlalchemy.orm import Session
    from app.api.schemas import TicketCreate
    from app.domain.enums import Role
    from app.manage import create_user, upgrade_database
    from app.repositories.database import get_engine
    from app.services.tickets import create_ticket
    from app.workers.checkpoints import setup_checkpoints
    from app.workers.runtime import run_once

    if args.mode == "api":
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=18003, access_log=False)
    elif args.mode == "worker":
        if args.run_id is None:
            raise SystemExit("必须指定本次测试 run-id")
        print(json.dumps({"processed": run_once(args.run_id)}))
    else:
        upgrade_database(get_engine())
        setup_checkpoints()
        prefix = f"e2e_{uuid4().hex[:12]}"
        users = {}
        for key, role in (("business", Role.BUSINESS), ("knowledge", Role.KNOWLEDGE_ADMIN)):
            password = secrets.token_urlsafe(24)
            with Session(get_engine(), expire_on_commit=False) as db:
                user = create_user(db, f"{prefix}_{key}", password, role)
                users[key] = {"login": user.login, "password": password}
                if key == "business":
                    for index in range(22):
                        create_ticket(db, user, str(uuid4()), TicketCreate(
                            customer_email="list@example.test", feedback_text=f"模拟列表工单 {prefix}-{index:02}",
                        ))
        # 父 Node 进程捕获此 JSON，不转发到日志，不把随机测试口令写入仓库。
        print(json.dumps(users))


if __name__ == "__main__":
    main()
