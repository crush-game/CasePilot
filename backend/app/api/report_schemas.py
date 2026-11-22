from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.api.quality_schemas import RuleId
from app.api.schemas import InputModel


class ReportRequest(InputModel):
    week_start: date | None = None


class WeeklyDeliveryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    report_id: UUID
    group_key: str
    mode: Literal["mock", "feishu"]
    status: Literal["queued", "sending", "sent", "failed", "unknown"]
    attempts: int
    receipt: str | None


class MetricRatio(BaseModel):
    count: int
    total: int


class QualityCoverage(BaseModel):
    total: int
    insufficient: int
    screened: int
    ai_checked: int
    reviewed: int


class FaultCounts(BaseModel):
    wifi: int
    other: int


class DeductionCount(BaseModel):
    rule_id: RuleId
    label: str
    count: int


class WeeklyMetrics(BaseModel):
    conversations: int
    self_resolved: MetricRatio
    handoff: MetricRatio
    new_tickets: int
    pending_human_at_cutoff: int
    faults: FaultCounts
    quality: QualityCoverage
    deductions: list[DeductionCount]


class WeeklyReportView(BaseModel):
    id: UUID
    week_start: date
    revision: int
    definition_version: str
    observed_at: datetime
    metrics_json: WeeklyMetrics
    deliveries: list[WeeklyDeliveryView]


class KnowledgeGapInput(InputModel):
    rule_id: RuleId
    statement: str = Field(min_length=1, max_length=1000)


class KnowledgeGapDecision(InputModel):
    decision: Literal["confirmed", "dismissed"]
    reason: str = Field(min_length=1, max_length=1000)


class KnowledgeGapView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_id: UUID
    rule_id: RuleId
    status: Literal["pending", "confirmed", "dismissed"]
    evidence_json: dict
    resolution_json: dict
