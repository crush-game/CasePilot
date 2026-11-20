"""人工触发的 P07 真实图小集，只发送公开虚构资料；程序总预算至多1元。"""

import asyncio
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
from uuid import UUID, uuid4

from dotenv import load_dotenv
import psycopg
from psycopg import sql
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.agents.contracts import AgentPolicy
from app.api.schemas import TicketCreate
from app.config import get_settings
from app.domain.enums import Role
from app.eval.live import CORPUS
from app.knowledge.hybrid import build_index
from app.knowledge.schemas import DocumentMetadata
from app.manage import create_user, upgrade_database
from app.providers.configuration import load_provider_config
from app.providers.ledger import ProviderFailure, budget_report, create_budget
from app.providers.remote import ProviderSession
from app.repositories.database import get_engine
from app.repositories.models import NodeRun, ProviderBudget, Run, Ticket
from app.services.knowledge import create_document
from app.services.tickets import create_ticket, digest
from app.services.workflow_common import latest_snapshot, ordered_nodes
from app.workers.checkpoints import setup_checkpoints
from app.workers.ingestion import run_once as ingest_once
from app.workers.runtime import run_once


def main():
    parser = argparse.ArgumentParser(description="P07真实模型路由小集，最多1元配置费率程序预算")
    parser.add_argument("--max-cost", type=float, default=1.0)
    args = parser.parse_args()
    if not 0 < args.max_cost <= 1:
        raise ProviderFailure("INVALID_PROVIDER_BUDGET")
    root = Path(__file__).resolve().parents[3]
    load_dotenv(root / ".env", encoding="utf-8-sig")
    settings = get_settings()
    if not settings.provider_api_key or not settings.provider_api_key.get_secret_value().strip():
        print(json.dumps({"passed": False, "real_acceptance": False, "error_code": "PROVIDER_KEY_MISSING"}))
        return 2
    config = load_provider_config(settings.provider_config_path)
    if any(profile.currency != "CNY" for profile in [config.chat, config.embedding, config.rerank, *config.chat_roles.values()]):
        raise ProviderFailure("LIVE_CNY_BUDGET_REQUIRED")
    source = make_url(os.environ.get("AFTERSALES_TEST_DATABASE_URL", ""))
    if source.host not in {"localhost", "127.0.0.1"} or source.database != "aftersales_test":
        raise ProviderFailure("LOCAL_TEST_DATABASE_REQUIRED")
    name = "aftersales_p07_live_" + uuid4().hex
    with psycopg.connect(**source.translate_connect_args(username="user", database="dbname"), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = source.set(database=name, drivername="postgresql+psycopg")
    engine = create_engine(url)
    report = {"passed": False, "real_acceptance": False, "database_name": name, "program_max_cost": args.max_cost,
              "currency": "CNY", "data_source": "mock", "cases": []}
    try:
        upgrade_database(engine)
        os.environ["AFTERSALES_DATABASE_URL"] = url.set(drivername="postgresql").render_as_string(hide_password=False)
        os.environ["AFTERSALES_WORKFLOW_GRAPH_VERSION"] = "supervisor-v1"
        get_settings.cache_clear()
        get_engine.cache_clear()
        setup_checkpoints()
        with Session(engine, expire_on_commit=False) as db:
            librarian = create_user(db, "p07_live_librarian", secrets.token_urlsafe(24), Role.KNOWLEDGE_ADMIN)
            actor = create_user(db, "p07_live_business", secrets.token_urlsafe(24), Role.BUSINESS)
            documents = [create_document(db, librarian, str(uuid4()), DocumentMetadata(doc_key="p07-live-" + key,
                version=1, title=title, product_scope=["PILOT-01"], firmware_versions=["1.0"], regions=["*"], channels=["*"]),
                key + ".md", ("# " + title + "\n" + text).encode()) for key, title, text in CORPUS]
        for value in documents:
            assert ingest_once(UUID(value["job_id"]))
        # 构建0.2元；两条独立工单各0.4元；新建库中无其他预算，合计至多1元配置费率额度。
        total_cost = Decimal(str(args.max_cost))
        build_budget = create_budget(engine, scope="p07-live-build", max_cost=Decimal("0.2") * total_cost, max_calls=10, max_tokens=50000)
        report["build"] = asyncio.run(build_index(ProviderSession(engine, build_budget, config, settings.provider_api_key)))
        if report["build"]["chunks"] != len(CORPUS):
            raise ProviderFailure("LIVE_CORPUS_NOT_READY")
        questions = [
            ("supported", "根据 PILOT-01 固件1.0的文档，P06NET-17断连时应该核对哪两项？", "PENDING_CONFIRMATION"),
            ("no_answer", "PILOT-01固件1.0是否有IP68防水认证？请按企业资料核实，没有资料请转人工。", "WAITING_HUMAN"),
        ]
        for kind, question, expected in questions:
            with Session(engine) as db:
                created = create_ticket(db, actor, str(uuid4()), TicketCreate(feedback_text=question,
                    customer_email="p07-synthetic@example.test", product_ref="PILOT-01", firmware_version="1.0"))
                run_id = UUID(created["run_id"])
                from app.repositories.models import CaseSnapshot
                row = db.scalar(select(CaseSnapshot).where(CaseSnapshot.run_id == run_id))
                state = {**row.state_json}
                state["agent_config"] = {**state["agent_config"], "policy": AgentPolicy(
                    max_cost=float(Decimal("0.4") * total_cost), max_run_cost=float(Decimal("0.4") * total_cost)).model_dump(mode="json")}
                row.state_json, row.checksum = state, digest(state)
                db.commit()
            if not run_once(run_id):
                raise ProviderFailure("LIVE_RUN_NOT_PROCESSED")
            with Session(engine) as db:
                run, ticket = db.get(Run, run_id), db.get(Ticket, UUID(created["ticket_id"]))
                state = latest_snapshot(db, run_id)
                nodes = ordered_nodes(db.scalars(select(NodeRun).where(NodeRun.run_id == run_id)))
                item = {"kind": kind, "question": question, "run_id": str(run_id), "status": ticket.status,
                    "stop_reason": run.stop_reason, "graph_version": run.graph_version, "inference_mode": state.get("inference_mode"),
                    "knowledge_report": state.get("knowledge_report"), "solution": ticket.solution_json,
                    "nodes": [{"name": node.node_name, "logical_step_id": node.logical_step_id,
                               "output_refs": node.output_refs, "usage": node.usage_json} for node in nodes]}
                report["cases"].append(item)
                if ticket.status != expected or state.get("inference_mode") != "real":
                    raise ProviderFailure("LIVE_ROUTING_NOT_VERIFIED")
                if kind == "supported" and (not ticket.solution_json.get("evidence_refs") or ticket.solution_json.get("reviewed")
                                            or "knowledge.assess" not in [node.node_name for node in nodes]):
                    raise ProviderFailure("LIVE_EVIDENCE_NOT_VERIFIED")
        report.update(passed=True, real_acceptance=True)
    except Exception as exc:
        report["error_code"] = getattr(exc, "code", "LIVE_SUITE_FAILED")
    finally:
        with Session(engine) as db:
            ids = list(db.scalars(select(ProviderBudget.id)))
        report["budgets"] = [budget_report(engine, identifier) for identifier in ids]
        report["configured_cost_exposure"] = sum(row["exposure_upper_bound"] for row in report["budgets"])
        output = root / "output/p07"
        output.mkdir(parents=True, exist_ok=True)
        (output / (name + ".json")).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if get_engine.cache_info().currsize:
            get_engine().dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()
        engine.dispose()
    print(json.dumps({key: report.get(key) for key in ("passed", "real_acceptance", "database_name", "error_code", "configured_cost_exposure")}))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProviderFailure as exc:
        print(json.dumps({"passed": False, "real_acceptance": False, "error_code": exc.code}))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"passed": False, "real_acceptance": False, "error_code": "LIVE_CONFIGURATION_OR_STORAGE_ERROR"}))
        raise SystemExit(2)
