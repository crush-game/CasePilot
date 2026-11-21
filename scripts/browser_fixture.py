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
    parser.add_argument("mode", choices=["prepare", "api", "worker", "faults", "fault-worker", "experience"])
    parser.add_argument("--run-id", type=UUID)
    parser.add_argument("--actor-id", type=UUID)
    parser.add_argument("--ticket-id", type=UUID)
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
    elif args.mode == "experience":
        from app.services.experiences import process_candidate
        if not args.ticket_id:
            raise SystemExit("必须指定本次测试工单")
        print(json.dumps({"processed": process_candidate(args.ticket_id)}))
    elif args.mode in {"faults", "fault-worker"}:
        # 仅浏览器验收夹具使用HTTP契约替身；业务代码不依赖tests。
        import sys
        from tempfile import TemporaryDirectory
        import httpx
        from pydantic import SecretStr
        sys.path.insert(0, str(root / "backend/tests/integration"))
        from test_p08 import advance, response, configuration
        from app.config import get_settings
        from app.providers.configuration import ProviderConfig
        from app.providers.ledger import create_budget
        from app.providers.remote import ProviderSession
        from app.repositories.models import AppUser
        from app.services.workflow_common import latest_snapshot
        def execute(run_id):
            with Session(get_engine()) as db:
                config = ProviderConfig.model_validate(latest_snapshot(db, run_id)["agent_config"]["providers"])
            client = ProviderSession(get_engine(), create_budget(get_engine(), scope="p08-browser-contract", max_calls=20),
                config, SecretStr("CONTRACT_TEST_KEY"), transport=httpx.MockTransport(response))
            advance(run_id, client)
        if args.mode == "fault-worker":
            if not args.run_id:
                raise SystemExit("必须指定本次测试run-id")
            execute(args.run_id)
            print(json.dumps({"processed": True, "inference_mode": "contract"}))
        else:
            if not args.actor_id:
                raise SystemExit("必须指定本次测试业务账号")
            with TemporaryDirectory(prefix="casepilot-p08-browser-") as directory:
                config_path = Path(directory) / "providers.json"
                config_path.write_text(configuration().model_dump_json(), encoding="utf-8")
                os.environ["AFTERSALES_WORKFLOW_GRAPH_VERSION"] = "supervisor-v2"
                os.environ["AFTERSALES_PROVIDER_CONFIG_PATH"] = str(config_path)
                os.environ["AFTERSALES_ENTERPRISE_MOCK_FIXTURE"] = "p08-demo"
                get_settings.cache_clear()
                cases = {}
                with Session(get_engine(), expire_on_commit=False) as db:
                    actor = db.get(AppUser, args.actor_id)
                    if not actor or not actor.login.startswith("e2e_") or actor.role != Role.BUSINESS:
                        raise SystemExit("只允许本次浏览器测试账号")
                    for name, email in (("cross", "p08-cross@example.test"), ("multi", "p08-multi@example.test")):
                        cases[name] = create_ticket(db, actor, str(uuid4()), TicketCreate(customer_email=email,
                            feedback_text="升级后断连，请核对WiFi和OTA的日志。", device_ref="P08-A", product_ref="PILOT-01",
                            firmware_version="1.0", platform="android", app_version="2.0", occurred_at="2026-11-20T10:00:00+08:00"))
                for value in cases.values():
                    execute(UUID(value["run_id"]))
                print(json.dumps(cases))
    else:
        upgrade_database(get_engine())
        setup_checkpoints()
        prefix = f"e2e_{uuid4().hex[:12]}"
        users = {}
        for key, role in (("business", Role.BUSINESS), ("knowledge", Role.KNOWLEDGE_ADMIN), ("consumer", Role.CONSUMER)):
            password = secrets.token_urlsafe(24)
            with Session(get_engine(), expire_on_commit=False) as db:
                user = create_user(db, f"{prefix}_{key}", password, role)
                users[key] = {"id": str(user.id), "login": user.login, "password": password}
                if key == "business":
                    for index in range(22):
                        create_ticket(db, user, str(uuid4()), TicketCreate(
                            customer_email="list@example.test", feedback_text=f"模拟列表工单 {prefix}-{index:02}",
                        ))
        # 父 Node 进程捕获此 JSON，不转发到日志，不把随机测试口令写入仓库。
        print(json.dumps(users))


if __name__ == "__main__":
    main()
