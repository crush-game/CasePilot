from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.api.schemas import InputModel


Scope = Annotated[list[Annotated[str, Field(min_length=1, max_length=120)]], Field(min_length=1, max_length=32)]


class DocumentMetadata(InputModel):
    doc_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$")
    version: int = Field(ge=1, le=1000000)
    title: str = Field(min_length=1, max_length=200)
    source_type: Literal["manual", "faq", "policy"] = "manual"
    data_source: Literal["mock"] = "mock"
    product_scope: Scope
    firmware_versions: Scope
    regions: Scope
    channels: Scope
    effective_from: AwareDatetime | None = None
    effective_to: AwareDatetime | None = None

    @model_validator(mode="after")
    def explicit_scope(self):
        for values in (self.product_scope, self.firmware_versions, self.regions, self.channels):
            if len(values) != len(set(values)) or "*" in values and len(values) != 1:
                raise ValueError("适用范围须去重；通用范围只能单独填写 *")
        if self.effective_from and self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("有效期必须为正向区间")
        return self


class View(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_serialization_defaults_required=True)


class DocumentView(View):
    id: UUID
    doc_key: str
    version: int
    revision: int
    title: str
    filename: str
    source_type: str
    data_source: Literal["mock"]
    retrieval_mode: Literal["bm25", "hybrid"]
    product_scope: list[str]
    firmware_versions: list[str]
    regions: list[str]
    channels: list[str]
    effective_from: datetime | None
    effective_to: datetime | None
    status: str
    checksum: str
    index_version: int | None
    created_at: datetime


class IngestionCreated(View):
    document_id: UUID
    job_id: UUID
    already_exists: bool


class DocumentActionResult(View):
    document_id: UUID
    revision: int
    status: str


class JobActionResult(View):
    job_id: UUID
    revision: int
    status: str


class JobView(View):
    id: UUID
    document_id: UUID
    status: str
    stage: str
    attempt: int
    revision: int
    error_code: str | None
    retryable: bool
    index_version: int | None
    history_json: list[dict]
    created_at: datetime


class DocumentList(View):
    items: list[DocumentView]
    next_cursor: UUID | None
    has_more: bool


class JobList(View):
    items: list[JobView]
    next_cursor: UUID | None
    has_more: bool


class KnowledgeAction(InputModel):
    action_id: UUID
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class KnowledgeScope(InputModel):
    product_ref: str | None = Field(default=None, min_length=1, max_length=120)
    firmware_version: str | None = Field(default=None, min_length=1, max_length=120)
    region: str | None = Field(default=None, min_length=1, max_length=120)
    channel: str | None = Field(default=None, min_length=1, max_length=120)
    as_of: AwareDatetime | None = None


class SearchQuery(KnowledgeScope):
    query: str = Field(min_length=1, max_length=500)
    limit: int = Field(default=20, ge=1, le=20)
    retrieval_mode: Literal["bm25", "hybrid"] | None = None
    rerank: bool = False


class Citation(View):
    ref: str
    chunk_id: UUID
    document_id: UUID
    doc_key: str
    document_version: int
    document_status: str
    title: str
    filename: str
    source_type: str
    source_checksum: str
    content_hash: str
    text: str
    heading_path: list[str]
    start_line: int
    end_line: int
    metadata: dict
    product_scope: list[str]
    firmware_versions: list[str]
    regions: list[str]
    channels: list[str]
    effective_from: datetime | None
    effective_to: datetime | None
    usable: bool
    missing_fields: list[str]
    unavailable_reasons: list[str]
    data_source: Literal["mock"] = "mock"
    retrieval_mode: Literal["bm25", "hybrid"] = "bm25"


class SearchHit(Citation):
    score: float
    rerank_score: float | None = None


class SearchResult(View):
    hits: list[SearchHit]
    missing_fields: list[str]
    index_version: int
    tokenizer: str
    retrieval_mode: Literal["bm25", "hybrid"] = "bm25"
    data_source: Literal["mock"] = "mock"
    embedding_profile_id: UUID | None = None
    inference_mode: Literal["none", "contract", "real"] = "none"
    rerank_mode: Literal["off", "contract", "real"] = "off"
    provider_usage: list[dict] = Field(default_factory=list)
    retrieval_details: dict = Field(default_factory=dict)


class SourceView(View):
    document_id: UUID
    filename: str
    source_checksum: str
    text: str
    redacted: Literal[True] = True
