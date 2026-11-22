from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from app.api.schemas import InputModel
from app.domain.enums import TicketStatus


SupportFlow = Literal["support-v1", "support-v2"]


class SupportMessage(InputModel):
    action_id: UUID
    conversation_id: UUID | None = None
    action: Literal["message", "clarify", "handoff", "solved", "submit_fault"] = "message"
    text: str = Field(default="", max_length=2000)
    product_ref: str | None = Field(default=None, min_length=1, max_length=120)
    firmware_version: str | None = Field(default=None, min_length=1, max_length=120)
    flow_version: SupportFlow | None = None
    device_ref: str | None = Field(default=None, min_length=1, max_length=128)
    platform: Literal["android", "ios"] | None = None
    app_version: str | None = Field(default=None, min_length=1, max_length=120)
    occurred_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def valid_action(self):
        if self.action == "message" and not self.text:
            raise ValueError("请填写问题")
        if self.action in {"clarify", "solved", "submit_fault"} and self.conversation_id is None:
            raise ValueError("请选择已有会话")
        return self


class HandoffOffer(BaseModel):
    question: str
    product_ref: str | None = None
    firmware_version: str | None = None
    missing_fields: list[Literal["product_ref", "firmware_version"]]


class SupportReply(BaseModel):
    kind: Literal["answer", "clarify", "handoff_offer", "handoff", "received", "feedback", "agent_reply", "investigation_queued"]
    text: str
    evidence_ref: str | None = None
    evidence_title: str | None = None
    service_window: str | None = None
    offer: HandoffOffer | None = None


class SupportTurnView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    request_text: str
    reply_json: SupportReply
    created_at: datetime


class SupportConversationView(BaseModel):
    id: UUID
    created_at: datetime
    ticket_no: str | None = None
    ticket_status: TicketStatus | None = None
    flow_version: SupportFlow = "support-v1"


class SupportDetail(SupportConversationView):
    turns: list[SupportTurnView]


class SupportAccepted(SupportConversationView):
    turn: SupportTurnView
