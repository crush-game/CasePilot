from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.dependencies import BusinessUser, Database, KnowledgeAdmin
from app.api.report_schemas import (
    KnowledgeGapDecision, KnowledgeGapInput, KnowledgeGapView, ReportRequest, WeeklyDeliveryView, WeeklyReportView,
)
from app.repositories.models import KnowledgeGap, WeeklyReport
from app.services import knowledge_gaps, weekly_reports


router = APIRouter(prefix="/api/v1")


@router.get("/reports/weekly", response_model=list[WeeklyReportView])
def list_reports(user: BusinessUser, db: Database, limit: int = Query(20, ge=1, le=100)):
    rows = db.scalars(select(WeeklyReport).order_by(WeeklyReport.week_start.desc(), WeeklyReport.revision.desc()).limit(limit))
    return [weekly_reports.view(db, row) for row in rows]


@router.post("/reports/weekly", response_model=WeeklyReportView)
def generate(body: ReportRequest, user: BusinessUser, db: Database):
    report = weekly_reports.generate(db, body.week_start)
    result = weekly_reports.view(db, report)
    db.commit()
    return result


@router.get("/reports/weekly/{report_id}", response_model=WeeklyReportView)
def detail(report_id: UUID, user: BusinessUser, db: Database):
    return weekly_reports.view(db, weekly_reports.report_for(db, report_id))


@router.post("/reports/weekly/{report_id}/delivery", response_model=WeeklyDeliveryView, status_code=202)
def enqueue(report_id: UUID, user: BusinessUser, db: Database):
    row = weekly_reports.enqueue(db, weekly_reports.report_for(db, report_id))
    result = WeeklyDeliveryView.model_validate(row)
    db.commit()
    return result


@router.post("/quality/assessments/{assessment_id}/knowledge-gap", response_model=KnowledgeGapView, status_code=201)
def submit_gap(assessment_id: UUID, body: KnowledgeGapInput, user: BusinessUser, db: Database):
    return knowledge_gaps.create(db, user, assessment_id, body)


@router.get("/knowledge-gaps", response_model=list[KnowledgeGapView])
def list_gaps(user: KnowledgeAdmin, db: Database, limit: int = Query(50, ge=1, le=100)):
    return list(db.scalars(select(KnowledgeGap).order_by(KnowledgeGap.created_at.desc(), KnowledgeGap.id).limit(limit)))


@router.post("/knowledge-gaps/{gap_id}/decision", response_model=KnowledgeGapView)
def resolve_gap(gap_id: UUID, body: KnowledgeGapDecision, user: KnowledgeAdmin, db: Database):
    return knowledge_gaps.resolve(db, user, gap_id, body)
