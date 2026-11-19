from datetime import datetime
from enum import StrEnum
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


Ref = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_:.-]{0,119}$")]
DeviceRef = Annotated[str, Field(min_length=1, max_length=128)]
Timestamp = Annotated[AwareDatetime, Field(strict=False)]


class ErrorCode(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    NO_FEEDBACK = "NO_FEEDBACK"
    NO_ATTACHMENT = "NO_ATTACHMENT"
    NO_MATCHING_RECORD = "NO_MATCHING_RECORD"
    DOWNLOAD_FAILED = "DOWNLOAD_FAILED"
    PARSE_FAILED = "PARSE_FAILED"
    UNSUPPORTED_DOMAIN = "UNSUPPORTED_DOMAIN"
    INVALID_ARGUMENTS = "INVALID_ARGUMENTS"
    FORBIDDEN = "FORBIDDEN"
    TOOL_NOT_ALLOWED = "TOOL_NOT_ALLOWED"
    TOOL_FAILED = "TOOL_FAILED"


class BoundArgs(Contract):
    customer_ref: Ref


class KnowledgeArgs(BoundArgs):
    query: str = Field(min_length=1, max_length=500)
    product_ref: Ref | None = None
    firmware_version: Ref | None = None
    region: str | None = Field(default=None, min_length=1, max_length=120)
    channel: str | None = Field(default=None, min_length=1, max_length=120)
    as_of: Timestamp | None = None
    retrieval_mode: Literal["bm25", "hybrid"] | None = None
    rerank: bool = False


class FeedbackArgs(BoundArgs):
    device_ref: DeviceRef | None = None
    platform: Literal["android", "ios"] | None = None
    occurred_at: Timestamp | None = None
    window_minutes: int = Field(default=30, ge=1, le=1440)


class DownloadArgs(BoundArgs):
    feedback_ref: Ref


class WindowArgs(BoundArgs):
    log_ref: Ref
    start: Timestamp
    end: Timestamp

    @model_validator(mode="after")
    def ordered_window(self):
        if not 0 < (self.end - self.start).total_seconds() <= 86400:
            raise ValueError("日志窗口必须为一天内的正向范围")
        return self


class WifiArgs(BoundArgs):
    window_ref: Ref


class DomainArgs(WifiArgs):
    domain: str = Field(min_length=1, max_length=30)


class KnowledgeRecord(Contract):
    record_id: Ref
    product_ref: str
    firmware_version: str
    policy_key: Ref
    text: str
    citation: dict | None = None


class KnowledgeData(Contract):
    documents: list[KnowledgeRecord] = Field(default_factory=list)
    conflicts: list[list[str]] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    retrieval_mode: Literal["fixture", "bm25", "hybrid"] = "fixture"
    index_version: int | None = None
    embedding_profile_id: str | None = None
    inference_mode: Literal["none", "contract", "real"] = "none"
    rerank_mode: Literal["off", "contract", "real"] = "off"
    provider_usage: list[dict] = Field(default_factory=list)
    retrieval_details: dict = Field(default_factory=dict)


class FeedbackRecord(Contract):
    record_id: Ref
    device_ref: DeviceRef
    platform: Literal["android", "ios"]
    occurred_at: Timestamp
    attachment_available: bool
    summary: str


class FeedbackData(Contract):
    records: list[FeedbackRecord] = Field(default_factory=list)
    requires_selection: bool = False
    missing_fields: list[str] = Field(default_factory=list)


class DownloadData(Contract):
    log_ref: Ref
    checksum: str
    size_bytes: int


class LogLine(Contract):
    record_id: Ref
    occurred_at: Timestamp
    domain: str
    text: str


class WindowData(Contract):
    window_ref: Ref
    snippets: list[LogLine]
    viewed_range: dict[str, datetime]
    missing_fields: list[str] = Field(default_factory=list)


class AnalysisData(Contract):
    analysis_mode: Literal["rule", "model"]
    domain: str
    findings: list[str]
    limitations: list[str]
    model_usage: dict | None = None


class Source(Contract):
    data_source: Literal["mock", "real"]
    adapter: str
    record_ids: list[str]
    query: dict


T = TypeVar("T", bound=Contract)


class ToolResult(Contract, Generic[T]):
    status: Literal["success", "no_data", "needs_human", "error"]
    data_source: Literal["mock", "real"]
    data_refs: list[str]
    data: T | None
    error_code: ErrorCode | None
    retryable: bool
    source: Source
    fetched_at: Timestamp
