from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, SecretStr, StringConstraints,
    field_validator, model_validator,
)

from app.domain.enums import HumanTaskStatus, Priority, Role, RunStatus, TicketStatus


LoginName = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=r"^[a-z0-9_.-]{3,64}$")]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginInput(InputModel):
    login: LoginName
    password: SecretStr = Field(min_length=1, max_length=128)


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    login: str
    role: Role


class LoginResult(BaseModel):
    user: UserView
    csrf_token: str


class TicketCreate(InputModel):
    feedback_text: str = Field(min_length=1, max_length=20000)
    customer_email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    device_ref: str | None = Field(default=None, min_length=1, max_length=128)
    occurred_at: AwareDatetime | None = None
    occurred_at_precision: Literal["minute", "second"] | None = None
    priority: Priority = Priority.NORMAL
    # 附件接口尚未交付时拒绝非空引用，不能接受后静默丢弃。
    artifact_ids: list[UUID] = Field(default_factory=list, max_length=0)

    @field_validator("customer_email")
    @classmethod
    def normalize_email(cls, value):
        local, domain = value.rsplit("@", 1)
        return f"{local}@{domain.lower()}"

    @model_validator(mode="after")
    def validate_precision(self):
        if self.occurred_at is None and self.occurred_at_precision is not None:
            raise ValueError("时间精度必须与发生时间一起提供")
        if self.occurred_at is not None and self.occurred_at_precision is None:
            self.occurred_at_precision = "second"
        return self


class TicketPatch(InputModel):
    action_id: UUID
    expected_version: int = Field(ge=1)
    priority: Priority | None = None
    assignee_id: UUID | None = None

    @model_validator(mode="after")
    def require_patch(self):
        fields = self.model_fields_set
        if not fields.intersection({"priority", "assignee_id"}):
            raise ValueError("至少提供优先级或负责人")
        if "priority" in fields and self.priority is None:
            raise ValueError("优先级不能为 null")
        return self


class TicketCreated(BaseModel):
    ticket_id: UUID
    ticket_no: str
    run_id: UUID
    task_id: UUID
    version: int
    status: TicketStatus


class TicketView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticket_no: str
    source: str
    data_source: Literal["mock"]
    customer_email: str
    feedback_text: str
    device_ref: str | None
    occurred_at: datetime | None
    occurred_at_original: str | None
    occurred_at_precision: str | None
    status: TicketStatus
    priority: Priority
    assignee_id: UUID | None
    version: int
    active_run_id: UUID | None
    created_at: datetime
    updated_at: datetime


class TicketDetail(TicketView):
    latest_event_id: int
    solution_json: dict = Field(default_factory=dict)
    result_json: dict = Field(default_factory=dict)
    human_task_id: UUID | None = None
    cancel_requested: bool = False


class TicketList(BaseModel):
    items: list[TicketView]
    next_cursor: str | None


class EventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    run_id: UUID | None
    event_type: str
    payload_json: dict
    created_at: datetime


class EventList(BaseModel):
    items: list[EventView]
    next_after_id: int
    has_more: bool


class RunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticket_id: UUID
    graph_version: str
    case_version: int
    status: RunStatus
    budget_json: dict
    stop_reason: str | None
    created_at: datetime
    checkpoint_ref: dict | None = None
    cancel_requested: bool = False
    nodes: list[dict] = Field(default_factory=list)


class VersionedAction(InputModel):
    action_id: UUID
    expected_version: int = Field(ge=1)


class FactsPatch(InputModel):
    device_ref: str | None = Field(default=None, min_length=1, max_length=128)
    occurred_at: AwareDatetime | None = None
    occurred_at_precision: Literal["minute", "second"] | None = None

    @model_validator(mode="after")
    def validate_fields(self):
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError("补充事实不能为 null")
        if self.occurred_at_precision and self.occurred_at is None:
            raise ValueError("时间精度必须与发生时间一起提供")
        return self


class ResumeInput(VersionedAction):
    facts_patch: FactsPatch = Field(default_factory=FactsPatch)
    selected_feedback_ref: None = None


class ReasonAction(VersionedAction):
    reason: str = Field(min_length=1, max_length=2000)


class ReinvestigateInput(ReasonAction):
    facts_patch: FactsPatch = Field(default_factory=FactsPatch)


class CloseInput(ReasonAction):
    outcome: Literal["resolved", "unresolved"]


class ReviewInput(VersionedAction):
    decision: Literal["approve", "revise"]
    reply_draft: str | None = Field(default=None, min_length=1, max_length=5000)


class FeedbackInput(ReasonAction):
    outcome: Literal["contacted", "resolved", "unresolved"]


class HumanTaskView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ticket_id: UUID
    run_id: UUID
    pause_key: str
    reason_code: str
    status: HumanTaskStatus
    assignee_id: UUID | None
    payload_json: dict
    created_at: datetime
    expected_version: int
    priority: Priority


class HumanTaskList(BaseModel):
    items: list[HumanTaskView]
    next_cursor: UUID | None


class ActionResult(BaseModel):
    ticket_id: UUID
    status: TicketStatus
    version: int
    run_id: UUID | None = None
    human_task_id: UUID | None = None
