import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

from app.api.schemas import TicketCreate
from app.api.support_schemas import SupportAccepted, SupportReply
from app.domain.errors import AppError
from app.domain.states import TERMINAL_STATUSES
from app.repositories.models import SupportConversation, SupportTurn, Ticket
from app.services.tickets import create_ticket, reserve_request
from app.services.workflow_common import append_event, lock_ticket
from app.tools.redaction import redact


PUBLIC_FAQ = Path(__file__).resolve().parents[3] / "fixtures/support/app-faq-v1.json"


def owned_conversation(db, owner_id, conversation_id, *, lock=False):
    query = select(SupportConversation).where(
        SupportConversation.owner_id == owner_id, SupportConversation.id == conversation_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise AppError(404, "SUPPORT_CONVERSATION_NOT_FOUND", "会话不存在")
    return row


def conversation_view(row, ticket):
    return {"id": row.id, "created_at": row.created_at, "ticket_no": ticket.ticket_no if ticket else None,
            "ticket_status": ticket.status if ticket else None}


def list_conversations(db, owner_id):
    rows = db.execute(select(SupportConversation, Ticket).outerjoin(Ticket).where(
        SupportConversation.owner_id == owner_id).order_by(SupportConversation.created_at.desc(),
                                                            SupportConversation.id.desc()).limit(50))
    return [conversation_view(row, ticket) for row, ticket in rows]


def detail(db, owner_id, conversation_id):
    row = owned_conversation(db, owner_id, conversation_id)
    turns = list(db.scalars(select(SupportTurn).where(SupportTurn.conversation_id == row.id)
                           .order_by(SupportTurn.id.desc()).limit(100)))
    return {**conversation_view(row, db.get(Ticket, row.ticket_id) if row.ticket_id else None), "turns": turns[::-1]}


def match_faq(question):
    normalized = "".join(question.casefold().split()).rstrip("？?。！!")
    entries = json.loads(PUBLIC_FAQ.read_text(encoding="utf-8"))["entries"]
    return next((row for row in entries if normalized in row["questions"]), None)


def reply_for(conversation, body):
    context = conversation.context_json
    if body.action == "solved":
        if context.get("last_kind") != "answer":
            raise AppError(409, "SUPPORT_ANSWER_REQUIRED", "当前没有待确认的回答")
        conversation.context_json = {"last_kind": "feedback"}
        return SupportReply(kind="feedback", text="已记录本次回答解决了问题。"), "", {}
    clarification = body.action == "clarify"
    if clarification and not context.get("pending_question"):
        raise AppError(409, "SUPPORT_CLARIFICATION_REQUIRED", "当前没有待补充的问题")
    if clarification:
        question = context["pending_question"]
    else:
        question = body.text or context.get("pending_question") or context.get("last_question") or "用户请求人工协助"
    scope = {key: getattr(body, key) or (context.get("scope", {}).get(key) if clarification or body.action == "handoff" else None)
             for key in ("product_ref", "firmware_version")}
    faq = match_faq(question) if body.action != "handoff" else None
    if faq:
        product = faq.get("product")
        if not product or (scope["product_ref"], scope["firmware_version"]) == (product, faq["firmware"]):
            conversation.context_json = {"last_kind": "answer", "last_question": redact(question), "scope": scope}
            return SupportReply(kind="answer", text=faq["answer"], evidence_ref=faq["ref"],
                                evidence_title=faq["title"]), question, scope
        if not clarification and (not scope["product_ref"] or not scope["firmware_version"]):
            conversation.context_json = {"pending_question": redact(question), "scope": scope}
            return SupportReply(kind="clarify", text="请补充设备型号和固件版本。"), question, scope
    return SupportReply(kind="handoff", text="已转人工。可在本会话查看工单进度。"), question, scope


def submit(db, actor, body, *, commit=True, source="app_support"):
    payload = body.model_dump(mode="json")
    record, replay = reserve_request(db, actor.id, "support.turn", str(body.action_id), payload)
    if replay:
        return record.response_ref

    if body.conversation_id:
        row = owned_conversation(db, actor.id, body.conversation_id, lock=True)
    else:
        row = SupportConversation(owner_id=actor.id, context_json={})
        db.add(row)
        db.flush()

    request_text = redact(body.text or {"clarify": "补充设备信息", "handoff": "转人工",
                                       "solved": "回答已解决问题"}.get(body.action, ""))
    if row.ticket_id:
        ticket = lock_ticket(db, row.ticket_id)
        if ticket.status in TERMINAL_STATUSES:
            raise AppError(409, "SUPPORT_THREAD_CLOSED", "此工单已结案，请开启新会话")
        if body.action not in {"message", "handoff"}:
            raise AppError(409, "SUPPORT_ALREADY_HANDED_OFF", "已转人工，请补充说明")
        append_event(db, ticket, "support.message_received", {"message": request_text})
        reply = SupportReply(kind="received", text="补充信息已记录到工单。")
    else:
        reply, question, scope = reply_for(row, body)
        ticket = None
        if reply.kind == "handoff":
            created = create_ticket(db, actor, str(row.id), TicketCreate(
                customer_email=f"consumer-{actor.id.hex}@example.test",
                feedback_text=redact(question), **scope,
            ), source=source, handoff=True, commit=False)
            ticket = db.get(Ticket, UUID(created["ticket_id"]))
            row.ticket_id = ticket.id
            row.context_json = {}

    turn = SupportTurn(conversation_id=row.id, request_text=request_text, reply_json=reply.model_dump(mode="json"))
    db.add(turn)
    db.flush()
    response = SupportAccepted(**conversation_view(row, ticket), turn=turn).model_dump(mode="json")
    record.response_ref = response
    if commit:
        db.commit()
    return response
