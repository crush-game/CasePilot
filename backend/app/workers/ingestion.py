"""独立知识入库 Worker；业务任务和索引快照均保存在 PostgreSQL。"""

import argparse
from dataclasses import dataclass
from datetime import timedelta
import json
from pathlib import Path
import time
from uuid import UUID, uuid4, uuid5

from dotenv import load_dotenv
import psycopg
from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.knowledge.index import index_state, publication_lock, refresh_snapshot
from app.knowledge.text import IngestionFailure, TOKENIZER, checksum, split_document
from app.repositories.database import get_engine
from app.repositories.models import IngestionJob, KBChunk, KBDocument
from app.services.knowledge import MAX_ATTEMPTS, audit
from app.workers.faults import failpoint


class IngestionLost(Exception):
    """已失效、归档或租约过期的执行结果不可发布。"""


@dataclass
class IngestionContext:
    job_id: UUID
    document_id: UUID
    token: UUID
    connection: object
    engine: object

    def fenced(self, db):
        if self.connection.closed:
            raise IngestionLost()
        self.connection.execute("SELECT 1")
        doc = db.scalar(select(KBDocument).where(KBDocument.id == self.document_id).with_for_update())
        job = db.scalar(select(IngestionJob).where(IngestionJob.id == self.job_id).with_for_update())
        now = db.scalar(select(func.clock_timestamp()))
        if (doc.status != "pending" or job.status != "running" or job.lease_token != self.token
                or job.lease_until is None or job.lease_until <= now):
            raise IngestionLost()
        return doc, job, now

    def advance(self, stage):
        with Session(self.engine) as db:
            _, job, now = self.fenced(db)
            job.stage, job.revision = stage, job.revision + 1
            job.lease_until = now + timedelta(seconds=get_settings().ingestion_lease_seconds)
            db.commit()


def claim(connection, candidate):
    engine = get_engine()
    with Session(engine, expire_on_commit=False) as db:
        doc = db.scalar(select(KBDocument).where(KBDocument.id == candidate.document_id).with_for_update(skip_locked=True))
        if doc is None:
            return None
        job = db.scalar(select(IngestionJob).where(IngestionJob.id == candidate.id).with_for_update(skip_locked=True))
        now = db.scalar(select(func.clock_timestamp()))
        if (job is None or doc.status != "pending" or job.status not in {"queued", "running"}
                or job.status == "running" and (job.lease_until is None or job.lease_until > now)):
            return None
        if job.attempt >= MAX_ATTEMPTS:
            doc.status, doc.revision = "failed", doc.revision + 1
            job.status, job.error_code, job.retryable = "failed", "ATTEMPT_LIMIT", False
            job.lease_token, job.lease_until = None, None
            job.revision += 1
            job.history_json = [*job.history_json, {"event": "failed", "stage": job.stage,
                "error_code": "ATTEMPT_LIMIT", "attempt": job.attempt, "at": now.isoformat()}]
            audit(doc, "ingestion_failed", error_code="ATTEMPT_LIMIT", stage=job.stage)
            db.commit()
            return "exhausted"
        job.status, job.stage, job.attempt, job.revision = "running", "parse", job.attempt + 1, job.revision + 1
        job.lease_token, job.lease_until = uuid4(), now + timedelta(seconds=get_settings().ingestion_lease_seconds)
        job.error_code, job.retryable = None, False
        job.history_json = [*job.history_json, {"event": "claimed", "attempt": job.attempt, "at": now.isoformat()}]
        db.commit()
        return IngestionContext(job.id, doc.id, job.lease_token, connection, engine), doc


def publish(ctx, parsed):
    with Session(ctx.engine) as db:
        publication_lock(db)
        doc, job, now = ctx.fenced(db)
        latest = db.scalar(select(func.max(KBDocument.version)).where(
            KBDocument.doc_key == doc.doc_key, KBDocument.index_version.is_not(None)))
        if latest is not None and doc.version <= latest:
            raise IngestionFailure("STALE_DOCUMENT_VERSION")
        old = db.scalar(select(KBDocument).where(KBDocument.doc_key == doc.doc_key, KBDocument.status == "active"))
        if old:
            old.status, old.revision = "superseded", old.revision + 1
            audit(old, "superseded", replacement_id=str(doc.id))
            db.flush()  # 先释放同 doc_key 活动版本唯一索引。
        ids = [uuid5(doc.id, f"chunk-v1:{ordinal}") for ordinal in range(len(parsed))]
        for ordinal, chunk in enumerate(parsed):
            db.add(KBChunk(id=ids[ordinal], document_id=doc.id, ordinal=ordinal, heading_path=chunk.heading_path,
                text=chunk.text, start_line=chunk.start_line, end_line=chunk.end_line, content_hash=checksum(chunk.text.encode()),
                metadata_json={"parser": "mdtxt-v1", "tokenizer": TOKENIZER, "redacted": True,
                    "parent_start_line": chunk.parent_start_line, "parent_end_line": chunk.parent_end_line,
                    "previous_ref": f"kb:{ids[ordinal - 1].hex}" if ordinal else None,
                    "next_ref": f"kb:{ids[ordinal + 1].hex}" if ordinal + 1 < len(ids) else None}))
        state = index_state(db)
        state.version += 1
        doc.status, doc.revision, doc.index_version = "active", doc.revision + 1, state.version
        audit(doc, "published", index_version=state.version, chunk_count=len(parsed))
        db.flush()
        refresh_snapshot(db, state)
        # 构建快照后再次检查期限；过期的慢执行整体回滚，不发布半份索引。
        ctx.connection.execute("SELECT 1")
        if job.lease_until <= db.scalar(select(func.clock_timestamp())):
            raise IngestionLost()
        job.status, job.stage, job.index_version = "succeeded", "done", state.version
        job.revision += 1
        job.lease_token, job.lease_until = None, None
        job.history_json = [*job.history_json, {"event": "published", "attempt": job.attempt,
                                              "index_version": state.version, "at": now.isoformat()}]
        db.commit()


def mark_failed(ctx, error):
    with Session(ctx.engine) as db:
        doc, job, now = ctx.fenced(db)
        doc.status, doc.revision = "failed", doc.revision + 1
        job.status, job.error_code = "failed", error.code
        job.retryable = error.retryable and job.attempt < MAX_ATTEMPTS
        job.revision += 1
        job.lease_token, job.lease_until = None, None
        job.history_json = [*job.history_json, {"event": "failed", "stage": job.stage,
            "error_code": error.code, "attempt": job.attempt, "at": now.isoformat()}]
        audit(doc, "ingestion_failed", error_code=error.code, stage=job.stage)
        db.commit()


def run_once(job_id=None):
    with Session(get_engine()) as db:
        query = select(IngestionJob.id, IngestionJob.document_id).where(or_(
            IngestionJob.status == "queued", and_(IngestionJob.status == "running", IngestionJob.lease_until <= func.clock_timestamp())))
        if job_id:
            query = query.where(IngestionJob.id == job_id)
        candidates = list(db.execute(query.order_by(IngestionJob.created_at, IngestionJob.id).limit(50)))
    for candidate in candidates:
        with psycopg.connect(get_settings().database_url.get_secret_value(), autocommit=True, connect_timeout=3) as conn:
            acquired = conn.execute("SELECT pg_try_advisory_lock(hashtextextended(%s, 5))", (f"ingestion:{candidate.id}",)).fetchone()[0]
            if not acquired:
                continue
            claimed = claim(conn, candidate)
            if claimed is None:
                continue
            if claimed == "exhausted":
                return True
            ctx, doc = claimed
            try:
                failpoint("after_ingestion_claim")
                if checksum(doc.original_bytes) != doc.checksum:
                    raise IngestionFailure("SOURCE_CHECKSUM_MISMATCH")
                parsed = split_document(doc.original_bytes, doc.filename)
                ctx.advance("chunk")
                ctx.advance("index")
                failpoint("before_ingestion_publish")
                publish(ctx, parsed)
            except IngestionLost:
                pass
            except Exception as exc:
                error = exc if isinstance(exc, IngestionFailure) else IngestionFailure("INGESTION_FAILED", retryable=True)
                try:
                    mark_failed(ctx, error)
                except (IngestionLost, SQLAlchemyError, psycopg.Error):
                    pass  # 存储/连接不可用时保留运行任务，租约到期后重新领取。
            return True
    return False


def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", encoding="utf-8-sig")
    parser = argparse.ArgumentParser(description="知识入库 Worker；不调用模型或向量服务")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--job-id", type=UUID)
    args = parser.parse_args()
    try:
        while True:
            try:
                processed = run_once(args.job_id)
            except (SQLAlchemyError, psycopg.Error):
                if args.once:
                    raise SystemExit("知识存储暂不可用，本次未完成处理。") from None
                print("知识存储暂不可用，等待下次检查。", flush=True)
                processed = False
            if args.once:
                print(json.dumps({"processed": processed, "mode": "ingestion"}))
                return
            if not processed:
                time.sleep(get_settings().worker_poll_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
