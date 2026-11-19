"""P06 真实接口小集；只发送此文件中公开的虚构产品资料。"""

import asyncio
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
from uuid import uuid4

import psycopg
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.knowledge.hybrid import build_index
from app.knowledge.index import search
from app.knowledge.schemas import DocumentMetadata, SearchQuery
from app.manage import create_user, upgrade_database
from app.providers.client import ModelClient, ModelProfile, ModelRequest, SolutionDraft
from app.providers.configuration import load_provider_config
from app.providers.ledger import ProviderFailure, budget_report, create_budget
from app.providers.remote import ProviderSession
from app.services.knowledge import create_document
from app.workers.ingestion import run_once


CORPUS = [
    ("wifi", "连接断开", "PILOT-01 固件1.0出现 P06NET-17 断连时，核对网络设置和故障时间，不能只根据错误码判断硬件根因。"),
    ("ota", "升级排查", "PILOT-01 出现 P06OTA-21 升级失败时核对固件版本、升级包和 OTA 日志。升级后的断连不能仅由时间先后确定因果。"),
    ("spec", "产品规格", "PILOT-01 固件1.0支持模拟2.4GHz网络，5GHz支持情况没有资料，不得自行补充。"),
    ("power", "熄火断连", "模拟设备随车辆熄火停止供电时可能断开连接，需要结合供电状态、说明和匹配日志人工验证。"),
    ("feedback", "反馈匹配", "同一客户有多个设备时，先按设备和平台筛选反馈，再结合发生时间。存在多条候选时交由人工确认，不默认选择最新反馈。"),
    ("privacy", "日志使用", "日志交给分析服务前先脱敏，只查看相关时间范围；无匹配日志不代表故障从未发生。"),
]

QUERIES = ["P06NET-17 怎么检查？", "P06OTA-21 升级失败如何排查？", "PILOT-01 支持什么频段？",
           "熄火以后设备离线怎么办？", "同一个邮箱有很多设备反馈时如何选择？", "没有查到日志，能否认定问题没发生？"]


def run_small_suite(engine, session):
    with Session(engine, expire_on_commit=False) as db:
        actor = create_user(db, "p06_live_admin", secrets.token_urlsafe(24), Role.KNOWLEDGE_ADMIN)
        documents = []
        for key, title, body in CORPUS:
            value = create_document(db, actor, str(uuid4()), DocumentMetadata(doc_key="p06-live-" + key, version=1,
                title=title, source_type="manual", product_scope=["P06-LIVE"], firmware_versions=["1.0"],
                regions=["*"], channels=["*"]), key + ".md", ("# " + title + "\n" + body).encode())
            documents.append(value)
    for value in documents:
        from uuid import UUID
        if not run_once(UUID(value["job_id"])):
            raise ProviderFailure("LIVE_INGESTION_NOT_PROCESSED")
    build = asyncio.run(build_index(session))
    rows, drafts = [], []
    for number, question in enumerate(QUERIES):
        with Session(engine) as db:
            result = search(db, SearchQuery(query=question, product_ref="P06-LIVE", firmware_version="1.0",
                                            retrieval_mode="hybrid", rerank=True), session)
        if not result.hits or result.inference_mode != session.mode or result.rerank_mode != session.mode:
            raise ProviderFailure("LIVE_RETRIEVAL_NOT_VERIFIED")
        rows.append({"query": question, "result": result.model_dump(mode="json")})
        if number < 2:
            profile = session.config.chat_roles.get("solution", session.config.chat)
            client = ModelClient({"solution": ModelProfile(provider="openai_compatible", model=profile.model)}, provider_session=session)
            draft, usage = client.complete(ModelRequest(role="solution", input={"question": question,
                "evidence": [hit.model_dump(mode="json") for hit in result.hits]},
                allowed_evidence_refs=[hit.ref for hit in result.hits], data_source="mock"), SolutionDraft)
            if not draft.evidence_refs:
                raise ProviderFailure("LIVE_EMPTY_CITATIONS")
            drafts.append({"query": question, "draft": draft.model_dump(mode="json"), "usage": usage.model_dump(mode="json")})
    return {"passed": True, "real_acceptance": session.mode == "real", "inference_mode": session.mode,
            "data_source": "mock", "scope": "synthetic transport/retrieval/schema smoke; not agent-effectiveness evaluation",
            "build": build, "retrieval_cases": rows, "drafts": drafts}


def main():
    from app.config import get_settings
    from app.repositories.database import get_engine
    settings = get_settings()
    if settings.provider_api_key is None or not settings.provider_api_key.get_secret_value().strip():
        print(json.dumps({"passed": False, "real_acceptance": False, "error_code": "PROVIDER_KEY_MISSING",
                          "message": "请只在本项目 .env 配置 AFTERSALES_PROVIDER_API_KEY；本次未创建试验库或发起模型请求。"}, ensure_ascii=False))
        return 2
    config = load_provider_config(settings.provider_config_path)
    source = make_url(os.environ.get("AFTERSALES_TEST_DATABASE_URL", ""))
    if source.host not in {"localhost", "127.0.0.1"} or source.database != "aftersales_test":
        raise SystemExit("真实小集只允许从本机 aftersales_test 配置创建隔离验证库。")
    name = "aftersales_p06_live_" + uuid4().hex
    with psycopg.connect(**source.translate_connect_args(username="user", database="dbname"), autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = source.set(database=name, drivername="postgresql+psycopg")
    engine = create_engine(url)
    report, session = {"passed": False, "real_acceptance": False, "database_name": name}, None
    try:
        upgrade_database(engine)
        # 只修改本 CLI 进程的目标；不修改 .env 或开发库，不发送已有业务资料。
        os.environ["AFTERSALES_DATABASE_URL"] = url.set(drivername="postgresql").render_as_string(hide_password=False)
        get_settings.cache_clear()
        get_engine.cache_clear()
        budget_id = create_budget(engine, scope="p06-real-small-suite", max_cost=Decimal("5"),
                                  currency=config.chat.currency, max_calls=60, max_tokens=500000, seconds=600)
        session = ProviderSession(engine, budget_id, config, settings.provider_api_key)
        report.update(run_small_suite(engine, session))
    except Exception as exc:
        report["error_code"] = getattr(exc, "code", "LIVE_SUITE_FAILED")
    finally:
        if session is not None:
            report["billing"] = budget_report(engine, session.budget_id)
        output = Path(__file__).resolve().parents[3] / "output" / "p06"
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{name}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if get_engine.cache_info().currsize:
            get_engine().dispose()
        get_engine.cache_clear()
        get_settings.cache_clear()
        engine.dispose()
    print(json.dumps({"passed": report["passed"], "real_acceptance": report["real_acceptance"],
        "database_name": name, "error_code": report.get("error_code"), "report": f"output/p06/{name}.json"}, ensure_ascii=False))
    return 0 if report["passed"] and report["real_acceptance"] else 2
