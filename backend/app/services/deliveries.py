from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.channel_schemas import DeliveryView
from app.domain.errors import AppError
from app.repositories.database import get_engine
from app.repositories.models import ChannelThread, SupportConversation, SupportDelivery, SupportTurn
from app.services.tickets import get_ticket, reserve_request
from app.services.workflow_common import append_event, audit_action, lock_ticket
from app.tools.redaction import redact


def enqueue(db, conversation_id, channel, text, *, reply_author_id=None, **metadata):
    row = SupportDelivery(conversation_id=conversation_id, channel=channel, reply_author_id=reply_author_id,
                          payload_json={"text": redact(text), **metadata})
    db.add(row)
    db.flush()
    return row


def view(row):
    return DeliveryView(id=row.id, channel=row.channel, status=row.status, attempts=row.attempts,
                        text=row.payload_json["text"], last_error=row.last_error,
                        provider_ref=row.provider_ref, created_at=row.created_at)


def list_replies(db, ticket_id):
    get_ticket(db, ticket_id)
    return [view(row) for row in db.scalars(select(SupportDelivery).join(SupportConversation).where(
        SupportConversation.ticket_id == ticket_id).order_by(SupportDelivery.created_at.desc(),
                                                              SupportDelivery.id.desc()).limit(50))]


def queue_agent_reply(db, actor, ticket_id, body):
    record, replay = reserve_request(db, actor.id, f"tickets.support-reply:{ticket_id}", str(body.action_id),
                                     body.model_dump(mode="json"))
    if replay:
        return record.response_ref
    ticket = lock_ticket(db, ticket_id, body.expected_version)
    if ticket.assignee_id != actor.id:
        raise AppError(403, "NOT_TASK_OWNER", "请先认领工单，再向消费者回复")
    conversation = db.scalar(select(SupportConversation).where(SupportConversation.ticket_id == ticket_id))
    if not conversation:
        raise AppError(409, "SUPPORT_CONVERSATION_REQUIRED", "此工单没有消费者会话")
    thread = db.scalar(select(ChannelThread).where(ChannelThread.conversation_id == conversation.id))
    row = enqueue(db, conversation.id, "mock" if thread else "app", body.text, reply_author_id=actor.id,
                  **({"reply_target": thread.reply_target} if thread else {}))
    result = view(row).model_dump(mode="json")
    append_event(db, ticket, "support.reply_queued", {"delivery_id": str(row.id)})
    audit_action(db, ticket, actor.id, body, "tickets.support_reply", {"delivery_id": str(row.id)})
    record.response_ref = result
    db.commit()
    return result


def deliver_once(delivery_id=None):
    # 两种演示适配器都只写本地数据库。可重试状态和回执与发送结果在同一事务。
    with Session(get_engine()) as db:
        query = select(SupportDelivery).where(SupportDelivery.status == "queued",
                                              SupportDelivery.available_at <= func.clock_timestamp())
        if delivery_id is not None:
            query = query.where(SupportDelivery.id == delivery_id)
        row = db.scalar(query.order_by(SupportDelivery.available_at, SupportDelivery.id).limit(1)
                        .with_for_update(skip_locked=True))
        if row is None:
            return False
        row.attempts += 1
        if row.channel == "mock" and row.attempts <= row.payload_json.get("simulated_failures", 0):
            row.last_error = "MOCK_DELIVERY_FAILED"
            if row.attempts == 3:
                row.status = "failed"
            else:
                row.available_at = db.scalar(select(func.clock_timestamp())) + timedelta(seconds=2 ** row.attempts)
        else:
            if row.channel == "app":
                turn = SupportTurn(conversation_id=row.conversation_id, request_text="",
                                   reply_json={"kind": "agent_reply", "text": row.payload_json["text"]})
                db.add(turn)
                db.flush()
                row.provider_ref = f"app:{turn.id}"
            else:
                row.provider_ref = f"mock:{row.id.hex}"
            row.status, row.last_error = "delivered", None
        db.commit()
        return True
