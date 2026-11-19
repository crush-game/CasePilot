import asyncio
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import json
import os
from uuid import UUID, uuid4

import httpx
from psycopg import sql
import psycopg
from pydantic import SecretStr
import pytest
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import Role
from app.domain.errors import AppError
from app.knowledge.hybrid import build_index, rrf
from app.knowledge.index import search
from app.knowledge.schemas import DocumentMetadata, KnowledgeAction, SearchQuery
from app.manage import create_user, upgrade_database
from app.providers.client import ModelClient, ModelFailure, ModelProfile, ModelRequest, SolutionDraft
from app.providers.configuration import EmbeddingConfig, ProviderConfig, ServiceProfile
from app.providers.ledger import ProviderFailure, budget_report, create_budget
from app.providers.remote import ProviderSession
from app.repositories.database import get_engine
from app.repositories.models import KBChunk, KBDocument, KBEmbedding, KBIndexState, ProviderBudget, ProviderCall
from app.services.knowledge import archive, create_document
from app.workers.ingestion import run_once


pytestmark = pytest.mark.integration


@pytest.fixture
def isolated(test_engine, monkeypatch):
    name = "aftersales_p06_" + uuid4().hex
    params = test_engine.url.translate_connect_args(username="user", database="dbname")
    with psycopg.connect(**params, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = create_engine(test_engine.url.set(database=name))
        try:
            upgrade_database(engine)
            monkeypatch.setenv("AFTERSALES_DATABASE_URL", engine.url.set(drivername="postgresql").render_as_string(hide_password=False))
            get_settings.cache_clear()
            get_engine.cache_clear()
            yield engine
        finally:
            if get_engine.cache_info().currsize:
                get_engine().dispose()
            get_engine.cache_clear()
            get_settings.cache_clear()
            engine.dispose()
            assert name.startswith("aftersales_p06_") and len(name) == 47
            admin.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(name)))


def configuration():
    common = {"base_url": "https://contract.invalid/v1", "timeout_seconds": 0.1, "max_input_tokens": 20000,
              "input_price_per_million": 0.4, "currency": "CNY", "price_version": "contract-only"}
    return ProviderConfig(config_version="contract-v1",
        chat=ServiceProfile(model="contract-chat", **common, max_output_tokens=300, output_price_per_million=1.0),
        embedding=EmbeddingConfig(model="contract-embed", **common, dimensions=3),
        rerank=ServiceProfile(model="contract-rerank", **common))


def handler(request):
    body = json.loads(request.content)
    if request.url.path.endswith("embeddings"):
        def vector(value):
            if "OTA" in value or "升级" in value:
                return [0, 3, 0]
            if "规格" in value:
                return [0, 0, 3]
            return [3, 0, 0]
        return httpx.Response(200, json={"model": body["model"], "data": [
            {"index": index, "embedding": vector(value)} for index, value in reversed(list(enumerate(body["input"])))],
            "usage": {"prompt_tokens": 30}})
    if request.url.path.endswith("rerank"):
        return httpx.Response(200, json={"results": [{"index": index, "relevance_score": 1 / (index + 1)}
            for index in range(len(body["documents"]))], "meta": {"billed_units": {"input_tokens": 30, "output_tokens": 0}}})
    system = json.loads(body["messages"][0]["content"])
    draft = {"internal_plan": "根据提供证据核对连接。", "reply_draft": "请人工验证步骤。", "data_source": system["data_source"],
             "evidence_refs": system["allowed_evidence_refs"], "reviewed": False}
    return httpx.Response(200, json={"model": body["model"], "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(draft)}}],
        "usage": {"prompt_tokens": 60, "completion_tokens": 20}}, headers={"x-siliconcloud-trace-id": "contract-trace"})


def remote(engine, callback=handler, **budget):
    identifier = create_budget(engine, scope="contract-only", **budget)
    return ProviderSession(engine, identifier, configuration(), SecretStr("CONTRACT_TEST_KEY"), transport=httpx.MockTransport(callback))


def model_request():
    return ModelRequest(role="solution", input={"question": "连接问题", "customer_email": "private@example.test"},
                        allowed_evidence_refs=["kb:test"])


def model(session):
    return ModelClient({"solution": ModelProfile(provider="openai_compatible", model="contract-chat")}, provider_session=session)


def seed(engine, content="连接诊断 E_WIFI_401 请检查连接设置。", version=1, key="p06-guide", provider_session=None):
    with Session(engine, expire_on_commit=False) as db:
        actor = create_user(db, "admin_" + uuid4().hex, "contract-password-only", Role.KNOWLEDGE_ADMIN)
        value = create_document(db, actor, str(uuid4()), DocumentMetadata(doc_key=key, version=version, title="模拟指南",
            product_scope=["P06"], firmware_versions=["1.0"], regions=["*"], channels=["*"]), "guide.md", content.encode())
    assert run_once(UUID(value["job_id"]), provider_session=provider_session)
    return value


def test_remote_json_usage_and_key_never_enter_ledger(isolated):
    sent = []
    def capture(request):
        sent.append(request)
        return handler(request)
    session = remote(isolated, capture)
    output, usage = model(session).complete(model_request(), SolutionDraft)
    assert output.evidence_refs == ["kb:test"] and output.data_source == "mock"
    assert usage.inference_mode == "contract" and usage.simulated and usage.input_tokens == 60 and usage.output_tokens == 20
    assert usage.cost > 0 and usage.call_ids
    assert "private@example.test" not in sent[0].content.decode()
    with Session(isolated) as db:
        call = db.get(ProviderCall, UUID(usage.call_ids[0]))
        assert call.request_hash and call.response_hash and call.provider_request_id == "contract-trace"
        assert "CONTRACT_TEST_KEY" not in str(call.profile_json) + str(call.usage_json)


def test_bad_json_repairs_once_and_keeps_both_costs(isolated):
    count = 0
    def malformed(request):
        nonlocal count
        count += 1
        response = handler(request)
        if count == 1:
            data = response.json()
            data["choices"][0]["message"]["content"] = "not JSON"
            return httpx.Response(200, json=data)
        return response
    session = remote(isolated, malformed)
    _, usage = model(session).complete(model_request(), SolutionDraft)
    assert usage.model_calls == 2 and usage.input_tokens == 120
    report = budget_report(isolated, session.budget_id)
    assert [row["status"] for row in report["calls"]] == ["failed", "succeeded"]
    assert report["calls"][0]["usage"]["cost"] > 0


@pytest.mark.parametrize("status,expected,count", [(401, "PROVIDER_AUTH_FAILED", 1), (429, "PROVIDER_RATE_LIMITED", 2), (503, "PROVIDER_UNAVAILABLE", 2)])
def test_http_failure_retry_is_bounded_and_does_not_echo_body(isolated, status, expected, count):
    session = remote(isolated, lambda _: httpx.Response(status, text="private provider body CONTRACT_TEST_KEY"))
    with pytest.raises(ModelFailure, match=expected):
        model(session).complete(model_request(), SolutionDraft)
    report = budget_report(isolated, session.budget_id)
    assert report["calls_used"] == count and report["exposure_upper_bound"] > 0
    assert all(row["usage"]["cost"] is None for row in report["calls"])
    assert "CONTRACT_TEST_KEY" not in json.dumps(report)


def test_actual_async_deadline_and_missing_usage_keep_reservation(isolated):
    async def slow(_):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})
    session = remote(isolated, slow)
    with pytest.raises(ModelFailure, match="PROVIDER_TIMEOUT"):
        model(session).complete(model_request(), SolutionDraft)
    assert budget_report(isolated, session.budget_id)["calls_used"] == 2


def test_retry_denied_by_budget_keeps_first_attempt_in_failure_usage(isolated):
    session = remote(isolated, lambda _: httpx.Response(503), max_calls=1)
    with pytest.raises(ModelFailure, match="PROVIDER_BUDGET_EXHAUSTED") as caught:
        model(session).complete(model_request(), SolutionDraft)
    assert caught.value.usage.model_calls == 1 and len(caught.value.usage.call_ids) == 1
    assert budget_report(isolated, session.budget_id)["calls_used"] == 1


def test_success_without_usage_is_unknown_and_keeps_cost_exposure(isolated):
    def missing(request):
        data = handler(request).json()
        data.pop("usage")
        return httpx.Response(200, json=data)
    session = remote(isolated, missing)
    _, usage = model(session).complete(model_request(), SolutionDraft)
    assert usage.input_tokens is usage.output_tokens is usage.cost is None
    assert usage.tokens_source == "estimated_upper_bound"
    assert budget_report(isolated, session.budget_id)["exposure_upper_bound"] > 0


@pytest.mark.parametrize("cap", [{"max_tokens": 1}, {"max_cost": Decimal("0.00000001")}])
def test_budget_preflight_prevents_http_and_ledger_call(isolated, cap):
    sent = []
    session = remote(isolated, lambda request: sent.append(request), **cap)
    with pytest.raises(ProviderFailure, match="PROVIDER_BUDGET_EXHAUSTED"):
        asyncio.run(session.aembed(["连接"]))
    assert not sent and budget_report(isolated, session.budget_id)["calls_used"] == 0


def test_repeated_invalid_json_stops_after_one_repair(isolated):
    def invalid(request):
        data = handler(request).json()
        data["choices"][0]["message"]["content"] = "invalid"
        return httpx.Response(200, json=data)
    session = remote(isolated, invalid)
    with pytest.raises(ModelFailure, match="INVALID_MODEL_OUTPUT") as caught:
        model(session).complete(model_request(), SolutionDraft)
    assert caught.value.usage.model_calls == 2
    assert all(call["status"] == "failed" for call in budget_report(isolated, session.budget_id)["calls"])


def test_duplicate_rerank_indices_reject_without_retry(isolated):
    session = remote(isolated, lambda _: httpx.Response(200, json={"results": [
        {"index": 0, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.8}]}))
    with pytest.raises(ProviderFailure, match="INVALID_RERANK_RESPONSE"):
        asyncio.run(session.arerank("问题", ["甲", "乙"]))
    assert budget_report(isolated, session.budget_id)["calls_used"] == 1


def test_embedding_dimensions_order_zero_and_profile_mismatch(isolated):
    session = remote(isolated)
    vectors, _ = asyncio.run(session.aembed(["连接", "OTA"]))
    assert vectors == [[1, 0, 0], [0, 1, 0]]
    def wrong(request):
        value = handler(request).json()
        value["data"][0]["embedding"] = [1, 0]
        return httpx.Response(200, json=value)
    with pytest.raises(ProviderFailure, match="INVALID_EMBEDDING_RESPONSE"):
        asyncio.run(remote(isolated, wrong).aembed(["连接"]))


def test_shared_budget_reservation_allows_only_one_concurrent_request(isolated):
    session = remote(isolated, max_calls=1)
    def call(_):
        try:
            asyncio.run(session.aembed(["连接"]))
            return "ok"
        except ProviderFailure as exc:
            return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(call, range(2))) == ["PROVIDER_BUDGET_EXHAUSTED", "ok"]
    assert budget_report(isolated, session.budget_id)["calls_used"] == 1


def test_pgvector_rrf_rerank_and_new_documents_share_published_profile(isolated):
    session = remote(isolated)
    seed(isolated)
    seed(isolated, "OTA 升级指南，请查看升级日志。", key="p06-ota")
    result = asyncio.run(build_index(session))
    with Session(isolated) as db:
        hits = search(db, SearchQuery(query="连接", product_ref="P06", firmware_version="1.0", rerank=True), session)
    assert hits.retrieval_mode == "hybrid" and hits.inference_mode == hits.rerank_mode == "contract"
    assert hits.embedding_profile_id == UUID(result["profile_id"]) and hits.hits
    assert hits.retrieval_details["fusion"] == "rrf-k60" and hits.hits[0].rerank_score is not None
    assert all(row["simulated"] for row in hits.provider_usage)
    from app.knowledge.adapter import DatabaseKnowledgeAdapter
    from app.tools.mock import ToolContext
    from app.tools.registry import ToolRegistry
    registry = ToolRegistry(DatabaseKnowledgeAdapter(ToolContext("p06-customer", "mock@example.test"), {}, isolated,
                                                     provider_session=session))
    traced = registry.call("search_knowledge", {"customer_ref": "p06-customer", "query": "连接", "product_ref": "P06",
                                               "firmware_version": "1.0", "rerank": True})
    assert traced.status == "success" and traced.data.embedding_profile_id == result["profile_id"]
    assert traced.data.inference_mode == "contract" and len(traced.data.provider_usage) == 2
    new = seed(isolated, "连接诊断新版本。", version=2, provider_session=session)
    with Session(isolated) as db:
        from app.repositories.models import KBDocument
        assert db.get(KBDocument, UUID(new["document_id"])).retrieval_mode == "hybrid"
        assert db.scalar(select(KBEmbedding.id).join(KBChunk).where(KBChunk.document_id == UUID(new["document_id"])))


def test_profile_switch_failure_does_not_change_active_release(isolated):
    session = remote(isolated)
    seed(isolated)
    first = asyncio.run(build_index(session))
    bad_config = session.config.model_copy(update={"embedding": session.config.embedding.model_copy(update={"model": "different-embed"})})
    def invalid(request):
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0, 0, 0]}]})
    failed = ProviderSession(isolated, session.budget_id, bad_config, SecretStr("CONTRACT_TEST_KEY"), transport=httpx.MockTransport(invalid))
    with pytest.raises(ProviderFailure, match="INVALID_EMBEDDING_RESPONSE"):
        asyncio.run(build_index(failed))
    with Session(isolated) as db:
        assert str(db.get(KBIndexState, 1).active_profile_id) == first["profile_id"]
        with pytest.raises(AppError) as exc:
            search(db, SearchQuery(query="连接", product_ref="P06", firmware_version="1.0"), failed)
        assert exc.value.code == "EMBEDDING_PROFILE_MISMATCH"


def test_database_rejects_dimension_profile_mismatch(isolated):
    session = remote(isolated)
    seed(isolated)
    asyncio.run(build_index(session))
    with Session(isolated) as db:
        row = db.scalar(select(KBEmbedding))
        row.dimensions, row.embedding = 2, [1, 0]
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        assert db.scalar(select(KBEmbedding.dimensions)) == 3


def test_archive_during_rerank_does_not_return_stale_hits(isolated):
    document = seed(isolated)
    session = remote(isolated)
    asyncio.run(build_index(session))
    def changed(request):
        if request.url.path.endswith("rerank"):
            with Session(isolated, expire_on_commit=False) as db:
                actor = create_user(db, "late_archive", "contract-password-only", Role.KNOWLEDGE_ADMIN)
                doc = db.get(KBDocument, UUID(document["document_id"]))
                archive(db, actor, doc.id, KnowledgeAction(action_id=uuid4(), expected_revision=doc.revision, reason="contract"))
        return handler(request)
    session.transport = httpx.MockTransport(changed)
    with Session(isolated) as db:
        with pytest.raises(AppError) as caught:
            search(db, SearchQuery(query="连接", product_ref="P06", firmware_version="1.0", rerank=True), session)
        assert caught.value.code == "KNOWLEDGE_CHANGED"


def test_explicit_hybrid_without_index_never_falls_back(isolated):
    with Session(isolated) as db:
        with pytest.raises(AppError) as exc:
            search(db, SearchQuery(query="连接", retrieval_mode="hybrid"))
        assert exc.value.code == "HYBRID_INDEX_NOT_READY"


def test_local_contract_suite_cannot_be_reported_as_real_acceptance(isolated):
    from app.eval.live import run_small_suite
    result = run_small_suite(isolated, remote(isolated))
    assert result["passed"] and not result["real_acceptance"]
    assert result["inference_mode"] == "contract" and len(result["retrieval_cases"]) == 6
    assert len(result["drafts"]) == 2


def test_rrf_weights_are_by_rank_and_union_is_deduplicated():
    result = dict(rrf(["a", "b"], ["b", "c"]))
    assert result["b"] == pytest.approx(1 / 62 + 1 / 61)
    assert len(result) == 3 and result["b"] > result["a"]
