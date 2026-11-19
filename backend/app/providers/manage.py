import argparse
import asyncio
from decimal import Decimal
import json
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy.engine import make_url

from app.providers.configuration import load_provider_config
from app.providers.ledger import ProviderFailure, budget_report, create_budget


def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", encoding="utf-8-sig")
    parser = argparse.ArgumentParser(description="项目专用 Provider 配置、预算和索引管理，不输出密钥")
    parser.add_argument("command", choices=["check-config", "create-budget", "build-index", "report"])
    parser.add_argument("--budget-id", type=UUID)
    parser.add_argument("--max-cost", type=Decimal, default=Decimal("5"))
    parser.add_argument("--max-calls", type=int, default=60)
    parser.add_argument("--max-tokens", type=int, default=500000)
    parser.add_argument("--seconds", type=int, default=600)
    args = parser.parse_args()
    try:
        from app.config import get_settings
        from app.repositories.database import get_engine
        settings = get_settings()
        config = load_provider_config(settings.provider_config_path)
        if args.command == "check-config":
            print(json.dumps({"config_version": config.config_version,
                "key_configured": bool(settings.provider_api_key and settings.provider_api_key.get_secret_value().strip()),
                "chat_model": config.chat.model, "embedding_model": config.embedding.model,
                "embedding_dimensions": config.embedding.dimensions, "rerank_model": config.rerank.model}, ensure_ascii=False))
            return 0
        url = make_url(settings.database_url.get_secret_value())
        if url.host not in {"localhost", "127.0.0.1"} or not url.database.startswith("aftersales"):
            raise ProviderFailure("LOCAL_PROJECT_DATABASE_REQUIRED")
        engine = get_engine()
        if args.command == "create-budget":
            identifier = create_budget(engine, scope="manual-provider-budget", max_cost=args.max_cost,
                currency=config.chat.currency, max_calls=args.max_calls, max_tokens=args.max_tokens, seconds=args.seconds)
            print(json.dumps({"budget_id": str(identifier), "currency": config.chat.currency, "max_cost": str(args.max_cost)}))
            return 0
        if args.budget_id is None:
            parser.error("此命令需要 --budget-id")
        if args.command == "report":
            print(json.dumps(budget_report(engine, args.budget_id), ensure_ascii=False))
            return 0
        from app.knowledge.hybrid import build_index
        from app.providers.remote import configured_session
        result = asyncio.run(build_index(configured_session(engine, args.budget_id)))
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except ProviderFailure as exc:
        print(json.dumps({"error_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"error_code": "PROVIDER_CONFIGURATION_OR_STORAGE_ERROR"}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
