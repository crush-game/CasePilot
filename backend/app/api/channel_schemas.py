from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field

from app.api.schemas import InputModel, VersionedAction


class MockEvent(InputModel):
    event_id: UUID
    sender_id: UUID
    conversation_ref: str = Field(min_length=1, max_length=120)
    issue_ref: str = Field(min_length=1, max_length=120)
    reply_target: str = Field(min_length=1, max_length=120)
    occurred_at: AwareDatetime
    sequence: int = Field(ge=1, le=2147483647)
    kind: Literal["message", "edit"] = "message"
    action: Literal["message", "handoff"] = "message"
    text: str = Field(min_length=1, max_length=2000)
    simulated_failures: int = Field(default=0, ge=0, le=3)


class ChannelAccepted(BaseModel):
    event_id: UUID
    disposition: Literal["processed", "historical", "edited", "closed"]
    delivery_id: UUID | None = None
    ticket_no: str | None = None


class SupportAgentReply(VersionedAction):
    text: str = Field(min_length=1, max_length=2000)


class DeliveryView(BaseModel):
    id: UUID
    channel: Literal["app", "mock"]
    status: Literal["queued", "delivered", "failed"]
    attempts: int
    text: str
    last_error: str | None
    provider_ref: str | None
    created_at: datetime
