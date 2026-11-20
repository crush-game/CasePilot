from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import timedelta
import json
import os
import queue
import subprocess
import sys
import threading
import time
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import psycopg
import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.knowledge.adapter import DatabaseKnowledgeAdapter
from app.knowledge.text import checksum, split_document
from app.main import app
from app.repositories.models import IngestionJob, KBChunk, KBDocument, KBIndexState
from app.tools.mock import ToolContext
from app.tools.registry import ToolRegistry
from app.workers import ingestion


pytestmark = pytest.mark.integration
CONTENT = "# 模拟连接指南\n## 故障步骤\n遇到 E_WIFI_401 时检查 PILOT-01 的连接设置。\nAuthorization: Bearer TEST_ONLY_SECRET\n请核对固件版本并人工验证。".encode()


@pytest.fixture
def admin_api(api, account_factory):
    client, _, _ = api
    user, password = account_factory(Role.KNOWLEDGE_ADMIN)
    response = client.post("/api/v1/auth/login", json={"login": user.login, "password": password})
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client, user


def meta(**changes):
    return {"doc_key": f"guide-{uuid4().hex}", "version": 1, "title": "模拟连接指南", "source_type": "manual",
            "product_scope": [f"P05-{uuid4().hex}"], "firmware_versions": ["1.0"], "regions": ["*"], "channels": ["*"], **changes}


def upload(client, metadata, raw=CONTENT, filename="guide.md", key=None):
    return client.post("/api/v1/knowledge/documents", data={"metadata": json.dumps(metadata)},
                       files={"file": (filename, raw, "text/plain")}, headers={"Idempotency-Key": key or str(uuid4())})


def ingest(client, metadata, **kwargs):
    response = upload(client, metadata, **kwargs)
    assert response.status_code == 202, response.text
    value = response.json()
    assert ingestion.run_once(UUID(value["job_id"]))
    return value


def search(client, metadata, **extra):
    response = client.post("/api/v1/knowledge/search", json={"query": "E_WIFI_401", "product_ref": metadata["product_scope"][0],
                                                           "firmware_version": "1.0", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def job(client, value):
    return client.get(f"/api/v1/knowledge/jobs/{value['job_id']}").json()


def document(client, value):
    return client.get(f"/api/v1/knowledge/documents/{value['document_id']}").json()


def advance_ingestion(job_id):
    # 正式Worker持续轮询；进程退出/租约到期后的第一次空轮询不代表恢复失败。
    deadline = time.monotonic() + 5
    while not ingestion.run_once(job_id):
        assert time.monotonic() < deadline, "入库任务在限定时间内未被领取"
        time.sleep(0.05)
    return True


def test_upload_queue_publish_bm25_citation_and_source_roundtrip(admin_api):
    client, _ = admin_api
    metadata = meta()
    response = upload(client, metadata)
    assert response.status_code == 202, response.text
    value = response.json()
    assert document(client, value)["status"] == "pending" and job(client, value)["status"] == "queued"
    assert not search(client, metadata)["hits"]
    assert ingestion.run_once(UUID(value["job_id"]))
    assert job(client, value)["status"] == "succeeded" and job(client, value)["stage"] == "done"
    result = search(client, metadata)
    assert result["retrieval_mode"] == "bm25" and result["tokenizer"] == "zh-bigram-v1"
    hit = result["hits"][0]
    assert hit["document_id"] == value["document_id"] and hit["document_version"] == 1 and hit["usable"]
    assert hit["source_checksum"] == checksum(CONTENT) and hit["heading_path"] == ["模拟连接指南", "故障步骤"]
    assert hit["start_line"] == 2 and hit["end_line"] == 5
    assert "TEST_ONLY_SECRET" not in json.dumps(result) and "[REDACTED]" in hit["text"]
    citation = client.get(f"/api/v1/knowledge/chunks/{hit['chunk_id']}", params={"product_ref": metadata["product_scope"][0], "firmware_version": "1.0"})
    assert citation.status_code == 200 and citation.json()["usable"]
    preview = client.get(f"/api/v1/knowledge/documents/{value['document_id']}/source")
    assert preview.status_code == 200 and preview.json()["source_checksum"] == checksum(CONTENT)
    assert "TEST_ONLY_SECRET" not in preview.text
    assert not ingestion.run_once(UUID(value["job_id"]))


def test_txt_upload_and_registered_tool_use_actual_published_index(admin_api, test_engine):
    client, _ = admin_api
    metadata = meta(firmware_versions=["*"])
    ingest(client, metadata, filename="spec.txt", raw="PILOT-01 产品规格 E_WIFI_401 连接说明。".encode())
    tools = ToolRegistry(DatabaseKnowledgeAdapter(ToolContext("customer-demo", "mock@example.test"), {}, test_engine))
    result = tools.call("search_knowledge", {"customer_ref": "customer-demo", "query": "产品规格", "product_ref": metadata["product_scope"][0]})
    assert result.status == "success" and result.data.retrieval_mode == "bm25"
    assert result.source.adapter == "knowledge-index-v1" and result.source.record_ids == result.data_refs
    assert result.data.documents[0].citation["source_checksum"] and result.data.documents[0].citation["heading_path"] == []
    assert tools.call("search_knowledge", {"customer_ref": "another-customer", "query": "产品规格"}).error_code == "FORBIDDEN"


def test_upload_deduplication_idempotency_and_immutable_versions(admin_api, test_engine):
    client, _ = admin_api
    metadata, key = meta(), str(uuid4())
    first = upload(client, metadata, key=key)
    assert first.status_code == 202
    assert upload(client, metadata, key=key).json() == first.json()
    duplicate = upload(client, metadata)
    assert duplicate.status_code == 202 and duplicate.json()["already_exists"]
    assert duplicate.json()["job_id"] == first.json()["job_id"]
    assert upload(client, metadata, raw=b"different", key=key).status_code == 409
    assert upload(client, metadata, raw=b"different").status_code == 409
    assert upload(client, {**metadata, "regions": ["CN"]}).status_code == 409
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(KBDocument).where(KBDocument.doc_key == metadata["doc_key"])) == 1


@pytest.mark.parametrize("raw,code", [(b"\xff\xfe", "INVALID_UTF8"), (b"\x00text", "INVALID_TEXT"), (b"  ", "EMPTY_DOCUMENT")])
def test_bad_files_leave_visible_failed_nonsearchable_jobs(admin_api, test_engine, raw, code):
    client, _ = admin_api
    metadata = meta()
    value = ingest(client, metadata, raw=raw)
    failed = job(client, value)
    assert failed["status"] == "failed" and failed["stage"] == "parse" and failed["error_code"] == code
    assert failed["retryable"] is False and document(client, value)["status"] == "failed"
    assert not search(client, metadata)["hits"]
    listed = client.get("/api/v1/knowledge/jobs", params={"status": "failed", "document_id": value["document_id"]}).json()
    assert listed["items"][0]["id"] == value["job_id"]
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(KBChunk).where(KBChunk.document_id == UUID(value["document_id"]))) == 0


def test_failed_publication_rolls_back_and_operator_can_retry_once(admin_api, test_engine, monkeypatch):
    client, _ = admin_api
    metadata = meta()
    old = ingest(client, metadata)
    value = upload(client, {**metadata, "version": 2}).json()

    def failure(*args):
        raise RuntimeError("private exception TEST_ONLY_SECRET")

    with monkeypatch.context() as scope:
        scope.setattr(ingestion, "refresh_snapshot", failure)
        assert ingestion.run_once(UUID(value["job_id"]))
    failed = job(client, value)
    assert failed["status"] == "failed" and failed["stage"] == "index" and failed["retryable"]
    assert "TEST_ONLY_SECRET" not in json.dumps(failed)
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(KBChunk).where(KBChunk.document_id == UUID(value["document_id"]))) == 0
    assert document(client, old)["status"] == "active"
    assert {hit["document_version"] for hit in search(client, metadata)["hits"]} == {1}
    path = f"/api/v1/knowledge/jobs/{value['job_id']}/retry"
    body = {"action_id": str(uuid4()), "expected_revision": failed["revision"], "reason": "已恢复索引构建"}
    response = client.post(path, json=body)
    assert response.status_code == 202 and client.post(path, json=body).json() == response.json()
    assert client.post(path, json={**body, "action_id": str(uuid4())}).status_code == 409
    assert ingestion.run_once(UUID(value["job_id"]))
    assert job(client, value)["status"] == "succeeded" and job(client, value)["attempt"] == 2
    assert {hit["document_version"] for hit in search(client, metadata)["hits"]} == {2}


def test_concurrent_retry_rechecks_revision_after_waiting_for_document_lock(admin_api, test_engine, monkeypatch):
    from app.domain.errors import AppError
    from app.knowledge.schemas import KnowledgeAction
    from app.services import knowledge
    client, actor = admin_api
    value = upload(client, meta()).json()

    def failed(*args):
        raise RuntimeError("temporary parser failure")

    with monkeypatch.context() as scope:
        scope.setattr(ingestion, "split_document", failed)
        assert ingestion.run_once(UUID(value["job_id"]))
    revision = job(client, value)["revision"]
    barrier, original = threading.Barrier(2), knowledge.document

    def lock_after_both_reads(*args, **kwargs):
        if kwargs.get("lock"):
            barrier.wait(timeout=10)
        return original(*args, **kwargs)

    def retry_once(_):
        body = KnowledgeAction(action_id=uuid4(), expected_revision=revision, reason="重试同一失败任务")
        with Session(test_engine) as db:
            try:
                knowledge.retry(db, actor, UUID(value["job_id"]), body)
                return 202
            except AppError as exc:
                return exc.status

    with monkeypatch.context() as scope:
        scope.setattr(knowledge, "document", lock_after_both_reads)
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(retry_once, range(2))) == [202, 409]


def test_exhausted_crash_attempts_stop_with_visible_failure(admin_api, test_engine):
    from app.services.knowledge import MAX_ATTEMPTS
    client, _ = admin_api
    value = upload(client, meta()).json()
    with Session(test_engine) as db:
        db.execute(update(IngestionJob).where(IngestionJob.id == UUID(value["job_id"])).values(attempt=MAX_ATTEMPTS))
        db.commit()
    assert ingestion.run_once(UUID(value["job_id"]))
    failed = job(client, value)
    assert failed["status"] == "failed" and failed["error_code"] == "ATTEMPT_LIMIT" and not failed["retryable"]
    assert not ingestion.run_once(UUID(value["job_id"]))


def test_new_version_failure_preserves_old_and_publication_supersedes_atomically(admin_api):
    client, _ = admin_api
    metadata = meta()
    old = ingest(client, metadata)
    old_hit = search(client, metadata)["hits"][0]
    failed = ingest(client, {**metadata, "version": 2}, raw=b"\xff")
    assert job(client, failed)["status"] == "failed" and document(client, old)["status"] == "active"
    new = ingest(client, {**metadata, "version": 3}, raw=CONTENT + "\n新修订步骤。".encode())
    assert document(client, old)["status"] == "superseded" and document(client, new)["status"] == "active"
    assert {row["document_version"] for row in search(client, metadata)["hits"]} == {3}
    historical = client.get(f"/api/v1/knowledge/chunks/{old_hit['chunk_id']}").json()
    assert not historical["usable"] and "document_superseded" in historical["unavailable_reasons"]
    assert historical["text"] == old_hit["text"]


def test_scope_missing_version_effective_range_and_archive_filter(admin_api):
    client, _ = admin_api
    metadata = meta(regions=["CN"], channels=["app"])
    value = ingest(client, metadata)
    assert not search(client, metadata)["hits"]
    missing = search(client, metadata, firmware_version=None)
    assert set(missing["missing_fields"]) == {"firmware_version", "region", "channel"}
    assert not search(client, metadata, region="US", channel="app")["hits"]
    assert not search(client, metadata, region="CN", channel="app", firmware_version="2.0")["hits"]
    assert search(client, metadata, region="CN", channel="app")["hits"]
    expired = meta(effective_from="2020-01-01T00:00:00Z", effective_to="2021-01-01T00:00:00Z")
    ingest(client, expired)
    assert not search(client, expired)["hits"]
    assert search(client, expired, as_of="2020-06-01T00:00:00Z")["hits"]
    before = document(client, value)
    path = f"/api/v1/knowledge/documents/{value['document_id']}/archive"
    body = {"action_id": str(uuid4()), "expected_revision": before["revision"], "reason": "政策已失效"}
    response = client.post(path, json=body)
    assert response.status_code == 200 and client.post(path, json=body).json() == response.json()
    assert client.post(path, json={**body, "action_id": str(uuid4())}).status_code == 409
    assert not search(client, metadata, region="CN", channel="app")["hits"]


def test_snapshot_corruption_and_new_process_rebuild_before_query(admin_api, test_engine):
    client, _ = admin_api
    metadata = meta()
    ingest(client, metadata)
    expected = search(client, metadata)
    with Session(test_engine) as db:
        state = db.get(KBIndexState, 1)
        state.snapshot_json = {"format": "old-format", "version": state.version - 1}
        db.commit()
    program = "from sqlalchemy.orm import Session; from app.repositories.database import get_engine; from app.knowledge.index import search; from app.knowledge.schemas import SearchQuery; import sys; db=Session(get_engine()); print(search(db,SearchQuery.model_validate_json(sys.argv[1])).model_dump_json()); db.close()"
    result = subprocess.run([sys.executable, "-c", program, json.dumps({"query": "E_WIFI_401", "product_ref": metadata["product_scope"][0], "firmware_version": "1.0"})],
                            capture_output=True, text=True, encoding="utf-8", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=30)
    assert result.returncode == 0, result.stderr
    rebuilt = json.loads(result.stdout)
    assert rebuilt["index_version"] == expected["index_version"] and rebuilt["hits"][0]["ref"] == expected["hits"][0]["ref"]


def test_parallel_versions_never_roll_back_newer_publication(admin_api, test_engine):
    client, _ = admin_api
    metadata = meta()
    first, second = upload(client, metadata).json(), upload(client, {**metadata, "version": 2}).json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert all(pool.map(lambda value: ingestion.run_once(UUID(value["job_id"])), [first, second]))
    assert document(client, second)["status"] == "active"
    assert document(client, first)["status"] in {"superseded", "failed"}
    assert {row["document_version"] for row in search(client, metadata)["hits"]} == {2}


@contextmanager
def held_ingestion(job_id, point):
    process = subprocess.Popen([sys.executable, "-m", "app.workers.ingestion", "--once", "--job-id", str(job_id)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env={**os.environ, "CASEPILOT_TEST_FAILPOINT": point})
    received, lines = queue.Queue(), []

    def reader():
        for line in process.stdout:
            lines.append(line)
            if line.strip() == f"P02_FAILPOINT:{point}":
                received.put(True)
        received.put(False)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    try:
        assert received.get(timeout=20), "".join(lines)
        yield process
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        thread.join(timeout=2)
        process.stdout.close()


@pytest.mark.parametrize("point", ["after_ingestion_claim", "before_ingestion_publish"])
def test_real_worker_kill_and_expired_lease_recover_without_partial_index(admin_api, test_engine, point):
    client, _ = admin_api
    metadata = meta()
    value = upload(client, metadata).json()
    job_id = UUID(value["job_id"])
    with held_ingestion(job_id, point):
        assert document(client, value)["status"] == "pending" and not search(client, metadata)["hits"]
        with Session(test_engine) as db:
            db.execute(update(IngestionJob).where(IngestionJob.id == job_id).values(lease_until=func.clock_timestamp() - timedelta(seconds=1)))
            db.commit()
        assert not ingestion.run_once(job_id)  # 旧进程仍持有运行锁，不能越过租约并发发布。
    assert advance_ingestion(job_id)
    assert job(client, value)["status"] == "succeeded" and job(client, value)["attempt"] == 2
    assert search(client, metadata)["hits"]


def test_recovery_worker_polls_until_running_lease_is_eligible(admin_api, test_engine):
    client, _ = admin_api
    value = upload(client, meta()).json()
    job_id = UUID(value["job_id"])
    with Session(test_engine) as db:
        db.execute(update(IngestionJob).where(IngestionJob.id == job_id).values(status="running", attempt=1,
            lease_until=func.clock_timestamp() + timedelta(seconds=1)))
        db.commit()
    assert not ingestion.run_once(job_id)
    assert advance_ingestion(job_id)
    assert job(client, value)["status"] == "succeeded" and job(client, value)["attempt"] == 2


def test_archiving_cancels_pending_job_and_blocks_late_publication(admin_api, test_engine):
    from app.config import get_settings
    client, _ = admin_api
    metadata = meta()
    value = upload(client, metadata).json()
    with psycopg.connect(get_settings().database_url.get_secret_value(), autocommit=True) as conn:
        with Session(test_engine) as db:
            candidate = db.execute(select(IngestionJob.id, IngestionJob.document_id).where(IngestionJob.id == UUID(value["job_id"]))).one()
        ctx, doc = ingestion.claim(conn, candidate)
        response = client.post(f"/api/v1/knowledge/documents/{value['document_id']}/archive", json={
            "action_id": str(uuid4()), "expected_revision": doc.revision, "reason": "停止此版本"})
        assert response.status_code == 200
        with pytest.raises(ingestion.IngestionLost):
            ingestion.publish(ctx, split_document(doc.original_bytes, doc.filename))
    assert job(client, value)["status"] == "cancelled" and not ingestion.run_once(UUID(value["job_id"]))


def test_upload_validation_permissions_and_admin_pagination(api, account_factory):
    client, business, password = api
    metadata = meta()
    assert upload(client, metadata).status_code == 403
    assert client.get("/api/v1/knowledge/jobs").status_code == 403
    with TestClient(app) as anonymous:
        assert anonymous.post("/api/v1/knowledge/search", json={"query": "连接"}).status_code == 401
    admin, admin_password = account_factory(Role.KNOWLEDGE_ADMIN)
    login = client.post("/api/v1/auth/login", json={"login": admin.login, "password": admin_password})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    for name in ("guide.pdf", "../guide.txt", "..\\guide.md"):
        assert upload(client, metadata, filename=name).status_code == 422
    # multipart 标准化 Windows 客户端的文件名；服务只收到 basename，不按它读取磁盘。
    windows = upload(client, metadata, filename="C:\\guide.md")
    assert windows.status_code == 202 and document(client, windows.json())["filename"] == "guide.md"
    assert upload(client, metadata, raw=b"x" * (1024 * 1024 + 1)).status_code == 413
    assert upload(client, {**metadata, "status": "active"}).status_code == 422
    created = ingest(client, metadata)
    upload(client, {**metadata, "version": 2})
    first = client.get("/api/v1/knowledge/documents", params={"doc_key": metadata["doc_key"], "limit": 1}).json()
    assert first["has_more"]
    second = client.get("/api/v1/knowledge/documents", params={"doc_key": metadata["doc_key"], "limit": 1, "cursor": first["next_cursor"]}).json()
    assert not second["has_more"] and first["items"][0]["id"] != second["items"][0]["id"]
    login = client.post("/api/v1/auth/login", json={"login": business.login, "password": password})
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert search(client, metadata)["hits"]
    assert client.get(f"/api/v1/knowledge/documents/{created['document_id']}/source").status_code == 403
