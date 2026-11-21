from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.api.schemas import InputModel
from app.domain.enums import TicketStatus


class SupportMessage(InputModel):
    action_id: UUID
    conversation_id: UUID | None = None
    action: Literal["message", "clarify", "handoff", "solved"] = "message"
    text: str = Field(default="", max_length=2000)
    product_ref: str | None = Field(default=None, min_length=1, max_length=120)
    firmware_version: str | None = Field(default=None, min_length=1, max_length=120)

    @model_validator(mode="after")
    def valid_action(self):
        if self.action == "message" and not self.text:
            raise ValueError("请填写问题")
        if self.action in {"clarify", "solved"} and self.conversation_id is None:
            raise ValueError("请选择已有会话")
        return self


class SupportReply(BaseModel):
    kind: Literal["answer", "clarify", "handoff", "received", "feedback", "agent_reply"]
    text: str
    evidence_ref: str | None = None
    evidence_title: str | None = None
    service_window: str | None = None


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


class SupportDetail(SupportConversationView):
    turns: list[SupportTurnView]


class SupportAccepted(SupportConversationView):
    turn: SupportTurnView
