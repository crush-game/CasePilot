from uuid import UUID

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.api.dependencies import BusinessUser, Database
from app.api.schemas import (
    ActionResult, CloseInput, FeedbackInput, HumanTaskList, HumanTaskView, ReasonAction,
    ReinvestigateInput, ResumeInput, ReviewInput, VersionedAction,
)
from app.domain.enums import HumanTaskStatus
from app.repositories.models import HumanTask, Ticket
from app.services import human


router = APIRouter(prefix="/api/v1")


@router.get("/human-tasks", response_model=HumanTaskList)
def list_human_tasks(
    user: BusinessUser, db: Database, status: HumanTaskStatus | None = None,
    assignee_id: UUID | None = None, cursor: UUID | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    query = select(HumanTask, Ticket).join(Ticket, Ticket.id == HumanTask.ticket_id)
    if status is not None:
        query = query.where(HumanTask.status == status)
    else:
        query = query.where(HumanTask.status.in_(human.OPEN_HUMAN_STATUSES))
    if assignee_id:
        query = query.where(HumanTask.assignee_id == assignee_id)
    if cursor:
        query = query.where(HumanTask.id > cursor)
    rows = list(db.execute(query.order_by(HumanTask.id).limit(limit + 1)))
    return {"items": [human.human_view(task, ticket) for task, ticket in rows[:limit]],
            "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None}


@router.get("/human-tasks/{task_id}", response_model=HumanTaskView)
def get_human_task(task_id: UUID, user: BusinessUser, db: Database):
    task = human.get_human_task(db, task_id)
    return human.human_view(task, db.get(Ticket, task.ticket_id))


@router.post("/human-tasks/{task_id}/claim", response_model=ActionResult)
def claim(task_id: UUID, body: VersionedAction, user: BusinessUser, db: Database):
    return human.claim(db, user, task_id, body)


@router.post("/human-tasks/{task_id}/resume", response_model=ActionResult, status_code=202)
def resume(task_id: UUID, body: ResumeInput, user: BusinessUser, db: Database):
    return human.resume(db, user, task_id, body)


@router.post("/tickets/{ticket_id}/takeover", response_model=ActionResult, status_code=202)
def takeover(ticket_id: UUID, body: ReasonAction, user: BusinessUser, db: Database):
    return human.takeover(db, user, ticket_id, body)


@router.post("/tickets/{ticket_id}/reinvestigate", response_model=ActionResult, status_code=202)
def reinvestigate(ticket_id: UUID, body: ReinvestigateInput, user: BusinessUser, db: Database):
    return human.reinvestigate(db, user, ticket_id, body)


@router.post("/tickets/{ticket_id}/review", response_model=ActionResult)
def review(ticket_id: UUID, body: ReviewInput, user: BusinessUser, db: Database):
    return human.review(db, user, ticket_id, body)


@router.post("/tickets/{ticket_id}/close", response_model=ActionResult)
def close(ticket_id: UUID, body: CloseInput, user: BusinessUser, db: Database):
    return human.close(db, user, ticket_id, body)


@router.post("/tickets/{ticket_id}/customer-feedback", response_model=ActionResult)
def feedback(ticket_id: UUID, body: FeedbackInput, user: BusinessUser, db: Database, response: Response):
    data = body.model_dump(exclude={"outcome"})
    if body.outcome == "resolved":
        return human.close(db, user, ticket_id, CloseInput(**data, outcome="resolved"), confirmation="customer_confirmed")
    if body.outcome == "unresolved":
        response.status_code = 202
        return human.reinvestigate(db, user, ticket_id, ReinvestigateInput(**data))
    return human.contacted(db, user, ticket_id, body)
