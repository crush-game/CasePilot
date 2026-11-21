from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas import InputModel


class PublicationCommand(InputModel):
    action_id: UUID
    reason: str = Field(min_length=1, max_length=2000)


class PublicationView(BaseModel):
    id: UUID
    experience_id: UUID
    revision: int
    status: Literal["active", "withdrawn"]
    conditions: dict[str, str]
    note: str
    withdrawal_note: str | None
    created_at: datetime


class RecallQuery(InputModel):
    query: str = Field(min_length=1, max_length=500)
    product_ref: str = Field(min_length=1, max_length=120)
    firmware_version: str = Field(min_length=1, max_length=120)
    platform: Literal["android", "ios"] | None = None
    app_version: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    channel: str | None = Field(default=None, max_length=120)


class ExperienceHint(BaseModel):
    publication_id: UUID
    revision: int
    source_ticket_id: UUID
    problem: str
    verified_steps: str
    conditions: dict[str, str]
    source_type: Literal["verified_case"] = "verified_case"
