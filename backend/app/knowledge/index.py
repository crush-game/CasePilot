from collections import Counter
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.domain.errors import AppError
from app.knowledge.schemas import Citation, KnowledgeScope, SearchHit, SearchQuery, SearchResult
from app.knowledge.text import TOKENIZER, bm25_scores, checksum, tokenize
from app.repositories.models import KBChunk, KBDocument, KBIndexState
from app.services.tickets import digest


def publication_lock(db: Session):
    db.execute(text("SELECT pg_advisory_xact_lock(671905001)"))


def index_state(db: Session) -> KBIndexState:
    state = db.get(KBIndexState, 1)
    if state is None:
        state = KBIndexState(id=1, version=0, snapshot_json={}, snapshot_checksum="")
        db.add(state)
        db.flush()
    return state


def active_chunks(db: Session):
    return list(db.execute(select(KBChunk, KBDocument).join(KBDocument)
                           .where(KBDocument.status == "active").order_by(KBChunk.id)))


def refresh_snapshot(db: Session, state: KBIndexState, rows=None):
    # 快照持久存 PostgreSQL，不依赖某个 Worker 的内存或本地缓存文件。
    rows = active_chunks(db) if rows is None else rows
    documents = {}
    for chunk, doc in rows:
        tokens = tokenize(" / ".join(chunk.heading_path) + "\n" + chunk.text)
        if tokens:
            documents[str(chunk.id)] = {"tf": dict(Counter(tokens)), "length": len(tokens)}
    state.snapshot_json = {"format": "bm25-v1", "tokenizer": TOKENIZER, "version": state.version,
        "corpus_hash": digest({str(chunk.id): checksum(chunk.text.encode()) for chunk, _ in rows}),
        "documents": documents}
    state.snapshot_checksum = digest(state.snapshot_json)
    db.flush()


def checked_snapshot(db: Session):
    state, rows = index_state(db), active_chunks(db)
    snapshot = state.snapshot_json if isinstance(state.snapshot_json, dict) else {}
    source_hash = digest({str(chunk.id): checksum(chunk.text.encode()) for chunk, _ in rows})
    if (snapshot.get("format") != "bm25-v1" or snapshot.get("tokenizer") != TOKENIZER
            or snapshot.get("version") != state.version or snapshot.get("corpus_hash") != source_hash
            or digest(snapshot) != state.snapshot_checksum):
        refresh_snapshot(db, state, rows)
    return state, rows


def applicability(doc: KBDocument, query: KnowledgeScope, now):
    missing, unavailable = [], []
    if doc.status != "active":
        unavailable.append(f"document_{doc.status}")
    at = query.as_of or now
    if doc.effective_from and at < doc.effective_from or doc.effective_to and at >= doc.effective_to:
        unavailable.append("outside_effective_range")
    for field, scope in (("product_ref", doc.product_scope), ("firmware_version", doc.firmware_versions),
                         ("region", doc.regions), ("channel", doc.channels)):
        value = getattr(query, field)
        if scope == ["*"]:
            continue
        if value is None:
            missing.append(field)
        elif value not in scope:
            unavailable.append(f"incompatible_{field}")
    return missing, unavailable


def citation_value(chunk: KBChunk, doc: KBDocument, query: KnowledgeScope, now):
    missing, unavailable = applicability(doc, query, now)
    if checksum(chunk.text.encode()) != chunk.content_hash:
        unavailable.append("content_hash_mismatch")
    return Citation(ref=f"kb:{chunk.id.hex}", chunk_id=chunk.id, document_id=doc.id, doc_key=doc.doc_key,
        document_version=doc.version, document_status=doc.status, title=doc.title, filename=doc.filename,
        source_type=doc.source_type, source_checksum=doc.checksum, content_hash=chunk.content_hash, text=chunk.text,
        heading_path=chunk.heading_path, start_line=chunk.start_line, end_line=chunk.end_line, metadata=chunk.metadata_json,
        product_scope=doc.product_scope, firmware_versions=doc.firmware_versions, regions=doc.regions, channels=doc.channels,
        effective_from=doc.effective_from, effective_to=doc.effective_to,
        usable=not missing and not unavailable, missing_fields=missing, unavailable_reasons=unavailable)


def search(db: Session, query: SearchQuery) -> SearchResult:
    publication_lock(db)
    state, rows = checked_snapshot(db)
    now = db.scalar(select(func.clock_timestamp()))
    lookup = {str(chunk.id): (chunk, doc) for chunk, doc in rows}
    hits, missing = [], set()
    for ref, score in bm25_scores(state.snapshot_json["documents"], query.query):
        chunk, doc = lookup[ref]
        value = citation_value(chunk, doc, query, now)
        if not value.unavailable_reasons:
            missing.update(value.missing_fields)
        if value.usable and len(hits) < query.limit:
            hits.append(SearchHit(**value.model_dump(), score=score))
    result = SearchResult(hits=hits, missing_fields=sorted(missing), index_version=state.version, tokenizer=TOKENIZER)
    db.commit()
    return result


def get_citation(db: Session, chunk_id: UUID, query: KnowledgeScope) -> Citation:
    publication_lock(db)
    row = db.execute(select(KBChunk, KBDocument).join(KBDocument).where(KBChunk.id == chunk_id)).first()
    if row is None:
        raise AppError(404, "CITATION_NOT_FOUND", "知识引用不存在")
    result = citation_value(*row, query, db.scalar(select(func.clock_timestamp())))
    db.commit()
    return result
