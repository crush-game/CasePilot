from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response
from sqlalchemy import delete, func, select

from app.api.dependencies import BusinessUser, CurrentUser, Database, require_trusted_origin
from app.api.schemas import (
    EventList, LoginInput, LoginResult, RunView, TicketCreate, TicketCreated, TicketDetail,
    TicketList, TicketPatch, TicketView, UserView, LogEvidenceView,
)
from app.config import get_settings
from app.domain.enums import Priority, TicketStatus
from app.domain.errors import AppError
from app.repositories.models import AuthSession, HumanTask, NodeRun, Run, TicketEvent, TicketFact
from app.services import auth, tickets


router = APIRouter(prefix="/api/v1")


@router.post("/auth/login", response_model=LoginResult, dependencies=[Depends(require_trusted_origin)])
def login(body: LoginInput, request: Request, response: Response, db: Database):
    user, token, csrf = auth.login(db, body.login, body.password.get_secret_value(), request.cookies.get(auth.COOKIE_NAME))
    response.set_cookie(
        auth.COOKIE_NAME, token, httponly=True, samesite="lax", path=auth.COOKIE_PATH,
        secure=get_settings().cookie_secure, max_age=get_settings().session_ttl_seconds,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"user": user, "csrf_token": csrf}


@router.get("/auth/me", response_model=UserView)
def me(user: CurrentUser):
    return user


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response, user: CurrentUser, db: Database):
    db.execute(delete(AuthSession).where(AuthSession.id == request.state.auth_session_id))
    db.commit()
    response.delete_cookie(auth.COOKIE_NAME, path=auth.COOKIE_PATH, secure=get_settings().cookie_secure, samesite="lax")


@router.post("/tickets", response_model=TicketCreated, status_code=202)
def create_ticket(
    body: TicketCreate, user: BusinessUser, db: Database,
    idempotency_key: Annotated[str, Header(min_length=1, max_length=128, pattern=r"^[\x21-\x7e]+$")],
):
    return tickets.create_ticket(db, user, idempotency_key, body)


@router.get("/tickets", response_model=TicketList)
def list_tickets(
    user: BusinessUser, db: Database, limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None, max_length=2048), status: TicketStatus | None = None,
    priority: Priority | None = None, assignee_id: UUID | None = None,
):
    return tickets.list_tickets(db, limit, cursor, status, priority, assignee_id)


@router.get("/tickets/{ticket_id}", response_model=TicketDetail)
def get_ticket(ticket_id: UUID, user: BusinessUser, db: Database):
    ticket = tickets.get_ticket(db, ticket_id)
    latest = db.scalar(select(func.max(TicketEvent.id)).where(TicketEvent.ticket_id == ticket_id)) or 0
    human_id = db.scalar(select(HumanTask.id).where(HumanTask.ticket_id == ticket_id, HumanTask.status.in_(["unclaimed", "claimed", "resuming"])))
    run = db.get(Run, ticket.active_run_id) if ticket.active_run_id else db.scalar(
        select(Run).where(Run.ticket_id == ticket_id).order_by(Run.created_at.desc(), Run.id.desc()).limit(1)
    )
    fact_rows = db.scalars(select(TicketFact).where(TicketFact.ticket_id == ticket_id)
                           .order_by(TicketFact.field, TicketFact.fact_version.desc()))
    facts = {}
    for fact in fact_rows:
        facts.setdefault(fact.field, fact)
    return TicketDetail(**TicketView.model_validate(ticket).model_dump(), latest_event_id=latest,
                        solution_json=ticket.solution_json, result_json=ticket.result_json,
                        human_task_id=human_id, cancel_requested=run.cancel_requested if run else False,
                        latest_run_id=run.id if run else None, facts=list(facts.values()))


@router.patch("/tickets/{ticket_id}", response_model=TicketView)
def update_ticket(ticket_id: UUID, body: TicketPatch, user: BusinessUser, db: Database):
    return tickets.patch_ticket(db, user, ticket_id, body)


@router.get("/tickets/{ticket_id}/events", response_model=EventList)
def events(
    ticket_id: UUID, user: BusinessUser, db: Database,
    after_id: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100),
):
    tickets.get_ticket(db, ticket_id)
    rows = list(db.scalars(select(TicketEvent).where(
        TicketEvent.ticket_id == ticket_id, TicketEvent.id > after_id,
    ).order_by(TicketEvent.id).limit(limit + 1)))
    items = rows[:limit]
    return {"items": items, "next_after_id": items[-1].id if items else after_id, "has_more": len(rows) > limit}


@router.get("/runs/{run_id}", response_model=RunView)
def get_run(run_id: UUID, user: BusinessUser, db: Database):
    run = db.get(Run, run_id)
    if not run:
        raise AppError(404, "RUN_NOT_FOUND", "运行记录不存在")
    from app.services.workflow_common import ordered_nodes
    nodes = ordered_nodes(db.scalars(select(NodeRun).where(NodeRun.run_id == run_id)))
    return RunView(**{name: getattr(run, name) for name in RunView.model_fields if name != "nodes"},
                   nodes=[{"id": str(node.id), "node_name": node.node_name, "status": node.status,
                           "logical_step_id": node.logical_step_id, "duration_ms": node.duration_ms,
                           "usage": node.usage_json, "input_refs": node.input_refs, "output_refs": node.output_refs} for node in nodes])


@router.get("/tickets/{ticket_id}/evidence/{evidence_id}", response_model=LogEvidenceView)
def get_log_evidence(ticket_id: UUID, evidence_id: UUID, user: BusinessUser, db: Database):
    from app.faults.tools import evidence_view
    tickets.get_ticket(db, ticket_id)
    return evidence_view(db, ticket_id, evidence_id)
