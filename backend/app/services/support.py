from datetime import datetime, timezone
import json
from pathlib import Path
import re
from uuid import UUID

from sqlalchemy import select

from app.api.schemas import TicketCreate
from app.api.support_schemas import SupportAccepted, SupportReply
from app.agents.contracts import configuration_snapshot
from app.config import get_settings
from app.domain.errors import AppError
from app.domain.states import TERMINAL_STATUSES
from app.providers.ledger import ProviderFailure
from app.repositories.models import SupportConversation, SupportTurn, Ticket
from app.services.tickets import create_ticket, get_ticket, reserve_request
from app.services.workflow_common import append_event, lock_ticket
from app.tools.redaction import redact


PUBLIC_FAQ = Path(__file__).resolve().parents[3] / "fixtures/support/app-faq-v1.json"
FAULT_FIELDS = ("device_ref", "platform", "app_version", "occurred_at")
WIFI_SYMPTOM = re.compile(r"wi[ -]?fi|无线|断连|断开|掉线|连不上", re.IGNORECASE)
OTHER_DOMAIN = re.compile(r"ota|升级失败|播放|黑屏|闪退|视频无法", re.IGNORECASE)


def owned_conversation(db, owner_id, conversation_id, *, lock=False):
    query = select(SupportConversation).where(
        SupportConversation.owner_id == owner_id, SupportConversation.id == conversation_id)
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise AppError(404, "SUPPORT_CONVERSATION_NOT_FOUND", "会话不存在")
    return row


def conversation_view(row, ticket):
    return {"id": row.id, "created_at": row.created_at, "ticket_no": ticket.ticket_no if ticket else None,
            "ticket_status": ticket.status if ticket else None, "flow_version": row.flow_version}


def list_conversations(db, owner_id):
    rows = db.execute(select(SupportConversation, Ticket).outerjoin(Ticket).where(
        SupportConversation.owner_id == owner_id).order_by(SupportConversation.created_at.desc(),
                                                            SupportConversation.id.desc()).limit(50))
    return [conversation_view(row, ticket) for row, ticket in rows]


def detail(db, owner_id, conversation_id):
    row = owned_conversation(db, owner_id, conversation_id)
    return detail_for(db, row, db.get(Ticket, row.ticket_id) if row.ticket_id else None)


def ticket_conversation(db, ticket_id):
    ticket = get_ticket(db, ticket_id)
    row = db.scalar(select(SupportConversation).where(SupportConversation.ticket_id == ticket.id))
    if row is None:
        raise AppError(404, "SUPPORT_CONVERSATION_NOT_FOUND", "此工单没有客服会话")
    return detail_for(db, row, ticket)


def detail_for(db, row, ticket):
    turns = list(db.scalars(select(SupportTurn).where(SupportTurn.conversation_id == row.id)
                           .order_by(SupportTurn.id.desc()).limit(100)))
    return {**conversation_view(row, ticket), "turns": turns[::-1]}


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
    scoped_turn = clarification or body.action in {"handoff", "submit_fault"}
    scope = {key: getattr(body, key) or (context.get("scope", {}).get(key) if scoped_turn else None)
             for key in ("product_ref", "firmware_version")}
    faq = match_faq(question) if body.action not in {"handoff", "submit_fault"} else None
    if faq:
        product = faq.get("product")
        if not product or (scope["product_ref"], scope["firmware_version"]) == (product, faq["firmware"]):
            conversation.context_json = {"last_kind": "answer", "last_question": redact(question), "scope": scope}
            return SupportReply(kind="answer", text=faq["answer"], evidence_ref=faq["ref"],
                                evidence_title=faq["title"]), question, scope
        if not clarification and (not scope["product_ref"] or not scope["firmware_version"]):
            conversation.context_json = {"pending_question": redact(question), "scope": scope}
            return SupportReply(kind="clarify", text="请补充设备型号和固件版本。"), question, scope
    if conversation.flow_version == "support-v2" and body.action not in {"handoff", "submit_fault"}:
        scope = {key: redact(value) if value else None for key, value in scope.items()}
        question = redact(question)
        conversation.context_json = {"pending_question": question, "scope": scope}
        offer = {"question": question, **scope, "missing_fields": [key for key, value in scope.items() if not value]}
        return SupportReply(kind="handoff_offer", text="可以把这条问题提交给客服继续处理。", offer=offer), question, scope
    calendar = get_settings().service_calendar
    notice = calendar.receipt(datetime.now(timezone.utc)) if calendar else "将在人工服务时间处理，进度以工单为准。"
    return SupportReply(kind="handoff", text="已转人工。可在本会话查看工单进度。",
                        service_window=notice), question, scope


def demo_investigation(actor, body, question, scope):
    if body.action != "submit_fault":
        return None, None
    settings = get_settings()
    devices = [device for device in settings.support_demo_devices.get(actor.id, [])
               if device.device_ref == body.device_ref]
    if len(devices) != 1:
        return None, None
    device = devices[0]
    if not WIFI_SYMPTOM.search(question) or OTHER_DOMAIN.search(question):
        return device, None
    if not all(getattr(body, field) for field in FAULT_FIELDS) or not all(scope.values()):
        return device, None
    if any(getattr(device, key) != value for key, value in {
        **scope, "platform": body.platform, "app_version": body.app_version,
    }.items()):
        return device, None
    try:
        return device, configuration_snapshot("supervisor-v2")
    except (ProviderFailure, OSError, ValueError):
        # 设备授权通过但调查环境缺失时，仍可建立人工工单。
        return device, None


def submit(db, actor, body, *, commit=True, source="app_support"):
    payload = body.model_dump(mode="json")
    for key in ("flow_version", *FAULT_FIELDS):
        if payload[key] is None:
            payload.pop(key)
    record, replay = reserve_request(db, actor.id, "support.turn", str(body.action_id), payload)
    if replay:
        return record.response_ref

    if body.conversation_id:
        row = owned_conversation(db, actor.id, body.conversation_id, lock=True)
        if body.flow_version and body.flow_version != row.flow_version:
            raise AppError(409, "SUPPORT_FLOW_CONFLICT", "会话已固定处理版本，请刷新后重试")
    else:
        row = SupportConversation(owner_id=actor.id, context_json={}, flow_version=body.flow_version or "support-v1")
        db.add(row)
        db.flush()

    if body.action == "submit_fault" and (source != "app_support" or row.flow_version != "support-v2"):
        raise AppError(409, "SUPPORT_FLOW_CONFLICT", "当前会话不能提交设备调查")
    request_text = redact(body.text or {"clarify": "补充设备信息", "handoff": "转人工",
                                       "solved": "回答已解决问题", "submit_fault": "提交设备故障"}.get(body.action, ""))
    if row.ticket_id:
        ticket = lock_ticket(db, row.ticket_id)
        if ticket.status in TERMINAL_STATUSES:
            raise AppError(409, "SUPPORT_THREAD_CLOSED", "此工单已结案，请开启新会话")
        if body.action not in {"message", "handoff", "submit_fault"}:
            raise AppError(409, "SUPPORT_ALREADY_HANDED_OFF", "已转人工，请补充说明")
        append_event(db, ticket, "support.message_received", {"message": request_text})
        reply = SupportReply(kind="received", text="补充信息已记录到工单。")
    else:
        reply, question, scope = reply_for(row, body)
        ticket = None
        if reply.kind == "handoff":
            device, execution = demo_investigation(actor, body, question, scope)
            facts = {field: getattr(body, field) for field in FAULT_FIELDS}
            if facts["device_ref"]:
                facts["device_ref"] = redact(facts["device_ref"])
            if facts["app_version"]:
                facts["app_version"] = redact(facts["app_version"])
            created = create_ticket(db, actor, str(row.id), TicketCreate(
                customer_email=device.customer_email if device else f"consumer-{actor.id.hex}@example.test",
                feedback_text=redact(question), **scope, **facts,
            ), source=source, handoff=execution is None, commit=False, execution=execution)
            ticket = db.get(Ticket, UUID(created["ticket_id"]))
            row.ticket_id = ticket.id
            row.context_json = {}
            if execution is not None:
                reply = SupportReply(kind="investigation_queued", text="设备故障已记录，正在等待首诊。")

    turn = SupportTurn(conversation_id=row.id, request_text=request_text, request_action=body.action,
                       reply_json=reply.model_dump(mode="json"))
    db.add(turn)
    db.flush()
    response = SupportAccepted(**conversation_view(row, ticket), turn=turn).model_dump(mode="json")
    record.response_ref = response
    if commit:
        db.commit()
    return response
