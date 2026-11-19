from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Query, UploadFile
from pydantic import ValidationError

from app.api.dependencies import CurrentUser, Database, KnowledgeAdmin
from app.domain.errors import AppError
from app.knowledge import index
from app.knowledge.schemas import (
    Citation, DocumentActionResult, DocumentList, DocumentMetadata, DocumentView,
    IngestionCreated, JobActionResult, JobList, JobView, KnowledgeAction, KnowledgeScope, SearchQuery, SearchResult, SourceView,
)
from app.knowledge.text import MAX_FILE_BYTES
from app.repositories.models import IngestionJob, KBDocument
from app.services import knowledge


router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


@router.post("/documents", status_code=202, response_model=IngestionCreated)
def upload_document(
    user: KnowledgeAdmin, db: Database, file: Annotated[UploadFile, File()],
    metadata: Annotated[str, Form(max_length=8192)],
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[\x21-\x7e]+$")],
):
    try:
        parsed = DocumentMetadata.model_validate_json(metadata)
    except ValidationError:
        raise AppError(422, "INVALID_METADATA", "文档元数据不符合要求，请检查适用范围和有效期") from None
    raw = file.file.read(MAX_FILE_BYTES + 1)
    return knowledge.create_document(db, user, idempotency_key, parsed, file.filename, raw)


@router.get("/documents", response_model=DocumentList)
def list_documents(user: KnowledgeAdmin, db: Database, limit: int = Query(20, ge=1, le=100),
                   cursor: UUID | None = None, status: Literal["pending", "active", "failed", "archived", "superseded"] | None = None,
                   doc_key: str | None = Query(None, max_length=120)):
    conditions = []
    if status:
        conditions.append(KBDocument.status == status)
    if doc_key:
        conditions.append(KBDocument.doc_key == doc_key)
    return knowledge.list_rows(db, KBDocument, conditions, cursor, limit)


@router.get("/documents/{document_id}", response_model=DocumentView)
def get_document(document_id: UUID, user: KnowledgeAdmin, db: Database):
    return knowledge.document(db, document_id)


@router.get("/documents/{document_id}/source", response_model=SourceView)
def source(document_id: UUID, user: KnowledgeAdmin, db: Database):
    return knowledge.source_preview(db, document_id)


@router.post("/documents/{document_id}/archive", response_model=DocumentActionResult)
def archive(document_id: UUID, body: KnowledgeAction, user: KnowledgeAdmin, db: Database):
    return knowledge.archive(db, user, document_id, body)


@router.get("/jobs", response_model=JobList)
def list_jobs(user: KnowledgeAdmin, db: Database, limit: int = Query(20, ge=1, le=100), cursor: UUID | None = None,
              status: Literal["queued", "running", "succeeded", "failed", "cancelled"] | None = None,
              document_id: UUID | None = None):
    conditions = []
    if status:
        conditions.append(IngestionJob.status == status)
    if document_id:
        conditions.append(IngestionJob.document_id == document_id)
    return knowledge.list_rows(db, IngestionJob, conditions, cursor, limit)


@router.get("/jobs/{job_id}", response_model=JobView)
def get_job(job_id: UUID, user: KnowledgeAdmin, db: Database):
    return knowledge.job(db, job_id)


@router.post("/jobs/{job_id}/retry", status_code=202, response_model=JobActionResult)
def retry(job_id: UUID, body: KnowledgeAction, user: KnowledgeAdmin, db: Database):
    return knowledge.retry(db, user, job_id, body)


@router.post("/search", response_model=SearchResult)
def search(body: SearchQuery, user: CurrentUser, db: Database):
    return index.search(db, body)


@router.get("/chunks/{chunk_id}", response_model=Citation)
def citation(chunk_id: UUID, user: CurrentUser, db: Database, query: Annotated[KnowledgeScope, Query()]):
    return index.get_citation(db, chunk_id, query)
