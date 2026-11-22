from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas import InputModel


RuleId = Literal["fatal_review", "business_incomplete", "process_late", "format_missing", "service_dismissive", "operation_model"]
QualityStatus = Literal["queued", "screened", "ai_queued", "pending_review", "finalized", "appealed", "insufficient"]


class QualityFinding(InputModel):
    rule_id: RuleId
    evidence: list[str] = Field(min_length=1, max_length=12)


class QualityJudgment(InputModel):
    findings: list[QualityFinding] = Field(max_length=12)


class QualityRuleSetInput(InputModel):
    version: str = Field(pattern=r"^v[0-9]{1,4}(\.[0-9]{1,4}){1,2}$")
    deductions: dict[Literal["business_incomplete", "process_late", "format_missing", "service_dismissive", "operation_model"], int]
    caps: dict[Literal["business", "process", "format", "service", "operation"], int]
    follow_up_minutes: int = Field(ge=1, le=10080)
    require_greeting: bool = False

    @model_validator(mode="after")
    def complete(self):
        if len(self.caps) != 5 or len(self.deductions) != 5:
            raise ValueError("质检版本须包含五个普通规则和五个维度")
        if any(not 0 <= value <= 100 for value in (*self.caps.values(), *self.deductions.values())):
            raise ValueError("维度上限与扣分须在 0～100")
        return self


class QualityBatchInput(InputModel):
    batch_key: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")
    random_pct: int = Field(ge=0, le=100, default=10)
    max_calls: int = Field(ge=0, le=200, default=20)
    ticket_id: UUID | None = None


class QualityDecision(InputModel):
    action_id: UUID
    expected_version: int = Field(ge=1)
    decision: Literal["confirm", "adjust", "appeal", "rescore"]
    reason: str = Field(min_length=1, max_length=1000)
    findings: list[QualityFinding] | None = Field(default=None, max_length=12)
    rule_version: str | None = Field(default=None, max_length=24)

    @model_validator(mode="after")
    def validate_decision(self):
        if (self.decision == "adjust") != (self.findings is not None):
            raise ValueError("仅调整时提交人工判定")
        if (self.decision == "rescore") != (self.rule_version is not None):
            raise ValueError("仅复评时指定规则版本")
        return self


class QualityBatchView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    batch_key: str
    ticket_id: UUID | None = None
    random_pct: int
    max_calls: int
    calls_used: int
    selection_json: list[dict]


class QualityView(BaseModel):
    id: UUID
    snapshot_id: UUID
    ticket_id: UUID
    subject_id: UUID
    subject_name: str
    rule_version: str
    status: QualityStatus
    version: int
    result_json: dict
    history_json: list[dict]
    created_at: datetime


class QualityDetail(QualityView):
    snapshot: dict


class QualityList(BaseModel):
    items: list[QualityView]
    next_cursor: UUID | None
    snapshot_missing: list[str]
