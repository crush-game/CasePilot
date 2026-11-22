from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import BusinessUser, Database, KnowledgeAdmin
from app.api.quality_schemas import (
    QualityBatchInput, QualityBatchView, QualityDecision, QualityDetail, QualityList, QualityRuleSetInput,
)
from app.repositories.models import QualityRuleSet
from app.services import quality


router = APIRouter(prefix="/api/v1/quality")


@router.get("/assessments", response_model=QualityList)
def assessments(user: BusinessUser, db: Database, ticket_id: UUID | None = None,
                cursor: UUID | None = None, limit: int = Query(20, ge=1, le=100)):
    return quality.list_assessments(db, ticket_id, cursor, limit)


@router.get("/assessments/{assessment_id}", response_model=QualityDetail)
def assessment(assessment_id: UUID, user: BusinessUser, db: Database):
    return quality.get_assessment(db, assessment_id)


@router.post("/assessments/{assessment_id}/decision", response_model=QualityDetail)
def decision(assessment_id: UUID, body: QualityDecision, user: BusinessUser, db: Database):
    return quality.decide(db, user, assessment_id, body)


@router.post("/batches", response_model=QualityBatchView)
def create_batch(body: QualityBatchInput, user: BusinessUser, db: Database):
    return quality.create_batch(db, body)


@router.get("/rules", response_model=list[QualityRuleSetInput])
def rules(user: BusinessUser, db: Database):
    return [{"version": row.version, **row.config_json}
            for row in db.scalars(select(QualityRuleSet).order_by(QualityRuleSet.created_at, QualityRuleSet.version))]


@router.post("/rules", response_model=QualityRuleSetInput, status_code=201)
def publish_rules(body: QualityRuleSetInput, user: KnowledgeAdmin, db: Database):
    return quality.publish_rules(db, body)
