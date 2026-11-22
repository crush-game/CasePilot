from uuid import UUID

from fastapi import APIRouter

from app.api.channel_schemas import ChannelAccepted, DeliveryView, MockEvent, SupportAgentReply
from app.api.dependencies import BusinessUser, Database
from app.api.support_schemas import SupportDetail
from app.services import channels, deliveries, support


router = APIRouter(prefix="/api/v1")


@router.post("/channels/mock/events", response_model=ChannelAccepted, status_code=202)
def mock_event(body: MockEvent, user: BusinessUser, db: Database):
    return channels.receive_mock(db, body)


@router.get("/channels/deliveries/{delivery_id}", response_model=DeliveryView)
def delivery(delivery_id: UUID, user: BusinessUser, db: Database):
    return channels.delivery(db, delivery_id)


@router.get("/tickets/{ticket_id}/support-replies", response_model=list[DeliveryView])
def support_replies(ticket_id: UUID, user: BusinessUser, db: Database):
    return deliveries.list_replies(db, ticket_id)


@router.get("/tickets/{ticket_id}/support-conversation", response_model=SupportDetail)
def support_conversation(ticket_id: UUID, user: BusinessUser, db: Database):
    return support.ticket_conversation(db, ticket_id)


@router.post("/tickets/{ticket_id}/support-replies", response_model=DeliveryView, status_code=202)
def support_reply(ticket_id: UUID, body: SupportAgentReply, user: BusinessUser, db: Database):
    return deliveries.queue_agent_reply(db, user, ticket_id, body)
