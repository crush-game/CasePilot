from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import BusinessUser, Database
from app.api.schemas import ExperienceList, ExperienceReviewInput, ExperienceView
from app.repositories.models import Experience
from app.services.experiences import review


router = APIRouter(prefix="/api/v1")


@router.get("/experiences", response_model=ExperienceList)
def list_experiences(
    user: BusinessUser, db: Database, status: Literal["candidate", "reviewed", "archived"] | None = None,
    ticket_id: UUID | None = None, cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100),
):
    query = select(Experience).where(Experience.status != "queued")
    if status:
        query = query.where(Experience.status == status)
    if ticket_id:
        query = query.where(Experience.source_ticket_id == ticket_id)
    if cursor:
        query = query.where(Experience.id > cursor)
    rows = list(db.scalars(query.order_by(Experience.id).limit(limit + 1)))
    return {"items": rows[:limit], "next_cursor": rows[limit - 1].id if len(rows) > limit else None}


@router.post("/experiences/{experience_id}/review", response_model=ExperienceView)
def review_experience(experience_id: UUID, body: ExperienceReviewInput, user: BusinessUser, db: Database):
    return review(db, user, experience_id, body)
