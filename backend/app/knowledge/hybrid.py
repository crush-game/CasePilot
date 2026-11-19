import asyncio
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.errors import AppError
from app.knowledge.index import active_chunks, applicability, checked_snapshot, citation_value, index_state, publication_lock, refresh_snapshot
from app.knowledge.schemas import SearchHit, SearchResult
from app.knowledge.text import TOKENIZER, bm25_scores, checksum
from app.providers.ledger import ProviderFailure
from app.providers.remote import configured_session
from app.repositories.models import EmbeddingProfile, KBChunk, KBDocument, KBEmbedding, KBIndexBuild


def embedding_text(chunk):
    return " / ".join(chunk.heading_path) + "\n" + chunk.text


def ensure_profile(session):
    config, mode = session.config.embedding, session.mode
    with Session(session.engine, expire_on_commit=False) as db:
        profile_id = db.scalar(insert(EmbeddingProfile).values(fingerprint=config.fingerprint(mode),
            dimensions=config.dimensions, inference_mode=mode, config_json=config.model_dump(mode="json"))
            .on_conflict_do_nothing(index_elements=["fingerprint"]).returning(EmbeddingProfile.id))
        profile = db.get(EmbeddingProfile, profile_id) if profile_id else db.scalar(
            select(EmbeddingProfile).where(EmbeddingProfile.fingerprint == config.fingerprint(mode)))
        db.commit()
        return profile


def require_profile(session, profile):
    if profile.fingerprint != session.config.embedding.fingerprint(session.mode):
        raise ProviderFailure("EMBEDDING_PROFILE_MISMATCH")


def batches(rows, profile):
    batch, size = [], 0
    for row in rows:
        amount = len(embedding_text(row).encode()) + 128
        if amount > min(8192, profile.max_input_tokens):
            raise ProviderFailure("EMBEDDING_INPUT_LIMIT")
        if batch and (len(batch) == 16 or size + amount > profile.max_input_tokens):
            yield batch
            batch, size = [], 0
        batch.append(row)
        size += amount
    if batch:
        yield batch


async def encode_chunks(session, chunks, before_attempt=None):
    encoded, usage = {}, []
    for batch in batches(chunks, session.config.embedding):
        vectors, measured = await session.aembed([embedding_text(chunk) for chunk in batch], before_attempt=before_attempt)
        usage.extend(measured["attempts"])
        for chunk, vector in zip(batch, vectors, strict=True):
            encoded[chunk.id] = {"embedding": vector, "content_hash": checksum(embedding_text(chunk).encode()),
                                 "provider_call_id": UUID(measured["call_id"])}
    return encoded, usage


async def build_index(session):
    profile = ensure_profile(session)
    with Session(session.engine, expire_on_commit=False) as db:
        publication_lock(db)
        state, rows = checked_snapshot(db)
        build = KBIndexBuild(profile_id=profile.id, budget_id=session.budget_id, base_version=state.version,
                             chunk_count=len(rows))
        db.add(build)
        db.commit()
        build_id, base_version = build.id, state.version
    try:
        chunks = [chunk for chunk, _ in rows]
        with Session(session.engine) as db:
            existing = {row.chunk_id: row.content_hash for row in db.scalars(select(KBEmbedding).where(KBEmbedding.profile_id == profile.id))}
        for chunk in chunks:
            if chunk.id in existing and existing[chunk.id] != checksum(embedding_text(chunk).encode()):
                raise ProviderFailure("EMBEDDING_CACHE_MISMATCH")
        missing = [chunk for chunk in chunks if chunk.id not in existing]
        for batch in batches(missing, session.config.embedding):
            encoded, _ = await encode_chunks(session, batch)
            with Session(session.engine) as db:
                for chunk_id, value in encoded.items():
                    db.execute(insert(KBEmbedding).values(chunk_id=chunk_id, profile_id=profile.id,
                        dimensions=profile.dimensions, **value).on_conflict_do_nothing(constraint="uq_kb_embeddings_chunk_profile"))
                db.commit()
        with Session(session.engine) as db:
            publication_lock(db)
            state = index_state(db)
            if state.version != base_version:
                raise ProviderFailure("KNOWLEDGE_CHANGED_DURING_BUILD")
            current = active_chunks(db)
            coverage = {row.chunk_id: row.content_hash for row in db.scalars(select(KBEmbedding).where(KBEmbedding.profile_id == profile.id))}
            if any(coverage.get(chunk.id) != checksum(embedding_text(chunk).encode()) for chunk, _ in current):
                raise ProviderFailure("HYBRID_INDEX_INCOMPLETE")
            state.active_profile_id, state.version = profile.id, state.version + 1
            for _, doc in current:
                doc.retrieval_mode = "hybrid"
            db.flush()
            refresh_snapshot(db, state)
            record = db.get(KBIndexBuild, build_id)
            record.status, record.index_version = "succeeded", state.version
            version = state.version
            db.commit()
        return {"build_id": str(build_id), "profile_id": str(profile.id), "index_version": version, "chunks": len(chunks)}
    except Exception as exc:
        code = exc.code if isinstance(exc, ProviderFailure) else "INDEX_BUILD_FAILED"
        with Session(session.engine) as db:
            record = db.get(KBIndexBuild, build_id)
            record.status, record.error_code = "failed", code
            db.commit()
        raise ProviderFailure(code) from None


def _scope_rows(rows, query, now):
    eligible, missing = {}, set()
    for chunk, doc in rows:
        gaps, unavailable = applicability(doc, query, now)
        if not unavailable:
            missing.update(gaps)
        if not gaps and not unavailable and checksum(chunk.text.encode()) == chunk.content_hash:
            eligible[str(chunk.id)] = (chunk, doc)
    return eligible, sorted(missing)


def rrf(*rankings):
    scores = {}
    for ranking in rankings:
        for rank, ref in enumerate(ranking, 1):
            scores[ref] = scores.get(ref, 0.0) + 1 / (60 + rank)
    return sorted(scores.items(), key=lambda row: (-row[1], row[0]))


def search(db, query, provider_session=None):
    from sqlalchemy import func
    publication_lock(db)
    state, rows = checked_snapshot(db)
    if state.active_profile_id is None:
        raise AppError(409, "HYBRID_INDEX_NOT_READY", "请先构建并发布完整的向量索引")
    profile = db.get(EmbeddingProfile, state.active_profile_id)
    profile_id, fingerprint, mode = profile.id, profile.fingerprint, profile.inference_mode
    eligible, missing = _scope_rows(rows, query, db.scalar(select(func.clock_timestamp())))
    version = state.version
    db.commit()
    if not eligible:
        return SearchResult(hits=[], missing_fields=missing, index_version=version, tokenizer=TOKENIZER,
                            retrieval_mode="hybrid", embedding_profile_id=profile_id, inference_mode=mode)
    try:
        session = provider_session or configured_session(db.get_bind())
        if session.config.embedding.fingerprint(session.mode) != fingerprint:
            raise ProviderFailure("EMBEDDING_PROFILE_MISMATCH")
        vectors, measured = asyncio.run(session.aembed([query.query]))
        usage = list(measured["attempts"])
        publication_lock(db)
        state, rows = checked_snapshot(db)
        if state.active_profile_id != profile_id:
            raise AppError(409, "KNOWLEDGE_CHANGED", "向量 profile 已变化，请重新检索")
        version = state.version
        eligible, missing = _scope_rows(rows, query, db.scalar(select(func.clock_timestamp())))
        ids = [UUID(ref) for ref in eligible]
        coverage = dict(db.execute(select(KBEmbedding.chunk_id, KBEmbedding.content_hash).where(
            KBEmbedding.profile_id == profile_id, KBEmbedding.chunk_id.in_(ids))).all())
        if any(coverage.get(chunk.id) != checksum(embedding_text(chunk).encode()) for chunk, _ in eligible.values()):
            raise ProviderFailure("HYBRID_INDEX_INCOMPLETE")
        lexical = [ref for ref, _ in bm25_scores(state.snapshot_json["documents"], query.query) if ref in eligible][:20]
        vector_ids = [str(value) for value in db.scalars(select(KBEmbedding.chunk_id).join(KBChunk).join(KBDocument)
            .where(KBEmbedding.profile_id == profile_id, KBEmbedding.dimensions == session.config.embedding.dimensions,
                   KBEmbedding.chunk_id.in_(ids), KBDocument.status == "active")
            .order_by(KBEmbedding.embedding.cosine_distance(vectors[0]), KBEmbedding.chunk_id).limit(20))]
        fused = rrf(lexical, vector_ids)
        candidates = [(citation_value(*eligible[ref], query, db.scalar(select(func.clock_timestamp())), retrieval_mode="hybrid"), score) for ref, score in fused]
        db.commit()
        rerank_scores = {}
        if query.rerank and candidates:
            selected, count = [], 0
            for value, score in candidates:
                amount = len(query.query.encode()) + len(embedding_text(value).encode()) + 128
                if count + amount > session.config.rerank.max_input_tokens:
                    break
                selected.append((value, score))
                count += amount
            if not selected:
                raise ProviderFailure("RERANK_INPUT_LIMIT")
            ordered, measured = asyncio.run(session.arerank(query.query, [embedding_text(value) for value, _ in selected]))
            usage.extend(measured["attempts"])
            candidates = [selected[index] for index, _ in ordered]
            rerank_scores = {selected[index][0].ref: score for index, score in ordered}
        publication_lock(db)
        state = index_state(db)
        if state.version != version or state.active_profile_id != profile_id:
            raise AppError(409, "KNOWLEDGE_CHANGED", "知识发布版本已变化，请重新检索")
        hits = [SearchHit(**value.model_dump(), score=score, rerank_score=rerank_scores.get(value.ref))
                for value, score in candidates[:min(query.limit, 6)]]
        result = SearchResult(hits=hits, missing_fields=missing, index_version=version, tokenizer=TOKENIZER,
            retrieval_mode="hybrid", embedding_profile_id=profile_id, inference_mode=mode,
            rerank_mode=session.mode if query.rerank else "off", provider_usage=usage,
            retrieval_details={"bm25_candidates": len(lexical), "vector_candidates": len(vector_ids),
                               "fusion": "rrf-k60", "rerank_candidates": len(rerank_scores)})
        db.commit()
        return result
    except ProviderFailure as exc:
        db.rollback()
        raise AppError(503, exc.code, "模型服务或预算不可用，本次检索未降级为 Mock/BM25") from None


def prepare_document(ctx, parsed):
    if ctx.embedding_profile_id is None:
        return None
    from uuid import uuid5
    session = ctx.provider_session or configured_session(ctx.engine)
    with Session(ctx.engine) as db:
        profile = db.get(EmbeddingProfile, ctx.embedding_profile_id)
        require_profile(session, profile)
        dimensions = profile.dimensions
    chunks = [SimpleNamespace(id=uuid5(ctx.document_id, f"chunk-v1:{index}"), text=value.text, heading_path=value.heading_path)
              for index, value in enumerate(parsed)]
    encoded, _ = asyncio.run(encode_chunks(session, chunks, before_attempt=lambda: ctx.advance("embedding")))
    return dimensions, encoded
