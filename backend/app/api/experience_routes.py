from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import BusinessUser, Database, KnowledgeAdmin
from app.api.schemas import ExperienceList, ExperienceReviewInput, ExperienceView
from app.repositories.models import Experience, ExperiencePublication
from app.services.experiences import review
from app.services import publications
from app.api.publication_schemas import ExperienceHint, PublicationCommand, PublicationView, RecallQuery


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


@router.get("/experience-release-candidates", response_model=list[ExperienceView])
def release_candidates(user: KnowledgeAdmin, db: Database, limit: int = Query(50, ge=1, le=100)):
    return list(db.scalars(select(Experience).where(Experience.status == "reviewed")
                          .order_by(Experience.created_at.desc(), Experience.id.desc()).limit(limit)))


@router.get("/experiences/{experience_id}/publications", response_model=list[PublicationView])
def release_history(experience_id: UUID, user: KnowledgeAdmin, db: Database):
    rows = db.scalars(select(ExperiencePublication).where(ExperiencePublication.experience_id == experience_id)
                      .order_by(ExperiencePublication.revision.desc()))
    return [publications.publication_view(row) for row in rows]


@router.post("/experiences/{experience_id}/publications", response_model=PublicationView, status_code=201)
def publish(experience_id: UUID, body: PublicationCommand, user: KnowledgeAdmin, db: Database):
    return publications.change_publication(db, user, experience_id, body)


@router.post("/experiences/{experience_id}/publications/{revision}/withdraw", response_model=PublicationView)
def withdraw(experience_id: UUID, revision: int, body: PublicationCommand, user: KnowledgeAdmin, db: Database):
    return publications.change_publication(db, user, experience_id, body, withdraw_revision=revision)


@router.post("/experience-recall", response_model=list[ExperienceHint])
def recall(body: RecallQuery, user: BusinessUser, db: Database):
    return publications.recall(db, body)
