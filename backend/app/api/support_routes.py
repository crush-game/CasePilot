from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.dependencies import CurrentUser, Database
from app.api.support_schemas import SupportAccepted, SupportConversationView, SupportDetail, SupportMessage
from app.domain.enums import Role
from app.domain.errors import AppError
from app.repositories.models import AppUser
from app.services import support


router = APIRouter(prefix="/api/v1/support")


def consumer_user(user: CurrentUser):
    if user.role != Role.CONSUMER:
        raise AppError(403, "ROLE_FORBIDDEN", "请使用消费者账号")
    return user


ConsumerUser = Annotated[AppUser, Depends(consumer_user)]


@router.get("/conversations", response_model=list[SupportConversationView])
def conversations(user: ConsumerUser, db: Database):
    return support.list_conversations(db, user.id)


@router.get("/conversations/{conversation_id}", response_model=SupportDetail)
def conversation(conversation_id: UUID, user: ConsumerUser, db: Database):
    return support.detail(db, user.id, conversation_id)


@router.post("/turns", response_model=SupportAccepted, status_code=201)
def turn(body: SupportMessage, user: ConsumerUser, db: Database):
    return support.submit(db, user, body)
