from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.api.channel_schemas import ChannelAccepted
from app.api.support_schemas import SupportMessage
from app.domain.enums import Role
from app.domain.errors import AppError
from app.domain.states import TERMINAL_STATUSES
from app.repositories.models import AppUser, ChannelEvent, ChannelThread, SupportConversation, Ticket
from app.services import support
from app.services.deliveries import enqueue, view
from app.services.tickets import digest
from app.tools.redaction import redact


def receive_mock(db, body):
    payload = body.model_dump(mode="json")
    signature = digest(payload)
    claimed = db.scalar(insert(ChannelEvent).values(id=body.event_id, request_hash=signature,
        event_json={**payload, "text": redact(body.text)}, response_json={}).on_conflict_do_nothing().returning(ChannelEvent.id))
    event = db.get(ChannelEvent, body.event_id)
    if claimed is None:
        if event.request_hash != signature:
            raise AppError(409, "CHANNEL_EVENT_CONFLICT", "同一渠道事件编号已用于不同内容")
        return event.response_json
    actor = db.get(AppUser, body.sender_id)
    if actor is None or actor.role != Role.CONSUMER or not actor.active:
        raise AppError(404, "CHANNEL_SENDER_NOT_FOUND", "模拟发送人必须绑定有效消费者账号")

    scope = {"sender_id": actor.id, "external_ref": body.conversation_ref, "issue_ref": body.issue_ref}
    db.execute(insert(ChannelThread).values(**scope, reply_target=body.reply_target, latest_sequence=0)
               .on_conflict_do_nothing(constraint="uq_channel_threads_issue"))
    thread = db.scalar(select(ChannelThread).filter_by(**scope).with_for_update())
    if thread.reply_target != body.reply_target:
        raise AppError(409, "CHANNEL_TARGET_CONFLICT", "会话回复目标已固定")
    event.thread_id = thread.id
    receipt = ChannelAccepted(event_id=event.id, disposition="processed")
    conversation = db.get(SupportConversation, thread.conversation_id) if thread.conversation_id else None
    ticket = db.get(Ticket, conversation.ticket_id) if conversation and conversation.ticket_id else None
    if body.kind == "edit":
        receipt.disposition = "edited"
    elif body.sequence <= thread.latest_sequence:
        receipt.disposition = "historical"
    elif ticket and ticket.status in TERMINAL_STATUSES:
        receipt.disposition = "closed"
    else:
        result = support.submit(db, actor, SupportMessage(
            action_id=uuid5(NAMESPACE_URL, f"casepilot-mock:{event.id}"), conversation_id=thread.conversation_id,
            action=body.action, text=body.text,
        ), commit=False, source="mock_channel")
        thread.conversation_id = UUID(result["id"])
        thread.latest_sequence = body.sequence
        reply = result["turn"]["reply_json"]
        notice = [reply["text"]]
        if result["ticket_no"]:
            notice.append(f'工单 {result["ticket_no"]}')
        if reply.get("service_window"):
            notice.append(reply["service_window"])
        row = enqueue(db, thread.conversation_id, "mock", "\n".join(notice), reply_target=thread.reply_target,
                      simulated_failures=body.simulated_failures)
        receipt.delivery_id = row.id
        receipt.ticket_no = result["ticket_no"]
    event.response_json = receipt.model_dump(mode="json")
    db.commit()
    return event.response_json


def delivery(db, delivery_id):
    from app.repositories.models import SupportDelivery
    row = db.get(SupportDelivery, delivery_id)
    if row is None:
        raise AppError(404, "DELIVERY_NOT_FOUND", "发送记录不存在")
    return view(row)
