from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import Session

from app.domain.errors import AppError
from app.knowledge.index import index_state, publication_lock, refresh_snapshot
from app.knowledge.schemas import DocumentMetadata
from app.knowledge.text import MAX_FILE_BYTES, checksum
from app.repositories.models import IngestionJob, KBDocument
from app.services.tickets import reserve_request
from app.tools.redaction import redact


MAX_ATTEMPTS = 5


def document(db, document_id, lock=False):
    query = select(KBDocument).where(KBDocument.id == document_id)
    row = db.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
    if row is None:
        raise AppError(404, "DOCUMENT_NOT_FOUND", "知识文档不存在")
    return row


def job(db, job_id, lock=False):
    query = select(IngestionJob).where(IngestionJob.id == job_id)
    row = db.scalar(query.with_for_update().execution_options(populate_existing=True) if lock else query)
    if row is None:
        raise AppError(404, "INGESTION_JOB_NOT_FOUND", "入库任务不存在")
    return row


def audit(row, event, actor_id=None, **values):
    row.audit_json = [*row.audit_json, {"event": event, "at": datetime.now(timezone.utc).isoformat(),
                                      "actor_id": str(actor_id) if actor_id else None, **values}]


def create_document(db: Session, actor, key: str, metadata: DocumentMetadata, filename: str, raw: bytes):
    if (not filename or len(filename) > 128 or any(char in filename for char in ("/", "\\", "\x00"))
            or not filename.lower().endswith((".md", ".txt"))):
        raise AppError(422, "UNSUPPORTED_FILE", "只接受名称合法的 UTF-8 Markdown/TXT 文件")
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise AppError(413 if raw else 422, "FILE_TOO_LARGE" if raw else "EMPTY_FILE", "文件须非空且不超过 1 MiB")
    payload = {**metadata.model_dump(mode="json"), "filename": filename, "checksum": checksum(raw)}
    record, replay = reserve_request(db, actor.id, "knowledge.upload", key, payload)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    # 同一文档键的并发上传串行，避免同版请求产生多个任务。
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 5))"), {"key": metadata.doc_key})
    existing = db.scalar(select(KBDocument).where(KBDocument.doc_key == metadata.doc_key, KBDocument.version == metadata.version))
    if existing:
        same = (existing.checksum == payload["checksum"] and existing.filename == filename
                and DocumentMetadata.model_validate({name: getattr(existing, name) for name in DocumentMetadata.model_fields}) == metadata)
        if not same:
            raise AppError(409, "DOCUMENT_VERSION_CONFLICT", "此版本已存在且内容或适用范围不同，请上传新版本")
        existing_job = db.scalar(select(IngestionJob).where(IngestionJob.document_id == existing.id))
        result = {"document_id": str(existing.id), "job_id": str(existing_job.id), "already_exists": True}
    else:
        doc = KBDocument(**metadata.model_dump(), filename=filename, checksum=payload["checksum"], original_bytes=raw, created_by=actor.id)
        db.add(doc)
        db.flush()
        doc.audit_json = []
        audit(doc, "uploaded", actor.id, checksum=doc.checksum)
        task = IngestionJob(document_id=doc.id)
        db.add(task)
        db.flush()
        result = {"document_id": str(doc.id), "job_id": str(task.id), "already_exists": False}
    record.response_ref = result
    db.commit()
    return result


def list_rows(db, model, conditions, cursor: UUID | None, limit):
    query = select(model).where(*conditions)
    if cursor:
        previous = db.get(model, cursor)
        if previous is None:
            raise AppError(422, "INVALID_CURSOR", "分页游标无效")
        query = query.where(tuple_(model.created_at, model.id) < tuple_(previous.created_at, previous.id))
    rows = list(db.scalars(query.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)))
    items = rows[:limit]
    return {"items": items, "next_cursor": items[-1].id if len(rows) > limit else None, "has_more": len(rows) > limit}


def archive(db, actor, document_id, body):
    record, replay = reserve_request(db, actor.id, f"knowledge.archive:{document_id}", str(body.action_id), body.model_dump(mode="json"))
    if replay:
        result = record.response_ref
        db.commit()
        return result
    publication_lock(db)
    doc = document(db, document_id, lock=True)
    if doc.revision != body.expected_revision:
        raise AppError(409, "VERSION_CONFLICT", "文档已变化，请刷新后重试")
    was_active = doc.status == "active"
    doc.status, doc.revision = "archived", doc.revision + 1
    audit(doc, "archived", actor.id, reason=body.reason, action_id=str(body.action_id))
    task = db.scalar(select(IngestionJob).where(IngestionJob.document_id == doc.id).with_for_update())
    if task.status in {"queued", "running"}:
        task.status, task.stage, task.revision = "cancelled", "cancelled", task.revision + 1
        task.lease_token, task.lease_until = None, None
    db.flush()
    if was_active:
        state = index_state(db)
        state.version += 1
        refresh_snapshot(db, state)
    result = {"document_id": str(doc.id), "revision": doc.revision, "status": doc.status}
    record.response_ref = result
    db.commit()
    return result


def retry(db, actor, job_id, body):
    record, replay = reserve_request(db, actor.id, f"knowledge.retry:{job_id}", str(body.action_id), body.model_dump(mode="json"))
    if replay:
        result = record.response_ref
        db.commit()
        return result
    original = job(db, job_id)
    doc = document(db, original.document_id, lock=True)
    task = job(db, job_id, lock=True)
    if task.revision != body.expected_revision:
        raise AppError(409, "VERSION_CONFLICT", "任务已变化，请刷新后重试")
    if task.status != "failed" or not task.retryable or doc.status == "archived" or task.attempt >= MAX_ATTEMPTS:
        raise AppError(409, "JOB_NOT_RETRYABLE", "任务不可重试；原文或版本错误请上传新版本")
    task.history_json = [*task.history_json, {"event": "retry_requested", "actor_id": str(actor.id),
        "reason": body.reason, "previous_error": task.error_code, "action_id": str(body.action_id)}]
    task.status, task.stage, task.error_code, task.retryable = "queued", "queued", None, False
    task.revision += 1
    task.lease_token, task.lease_until = None, None
    doc.status, doc.revision = "pending", doc.revision + 1
    audit(doc, "retry_requested", actor.id, job_id=str(task.id))
    result = {"job_id": str(task.id), "revision": task.revision, "status": task.status}
    record.response_ref = result
    db.commit()
    return result


def source_preview(db, document_id):
    doc = document(db, document_id)
    try:
        text = doc.original_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AppError(422, "INVALID_UTF8", "原文不是 UTF-8，请查看失败任务并上传新版本") from None
    return {"document_id": doc.id, "filename": doc.filename, "source_checksum": doc.checksum,
            "text": "\n".join(redact(line) for line in text.splitlines()), "redacted": True}
