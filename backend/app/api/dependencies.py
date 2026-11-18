import secrets
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.enums import Role
from app.domain.errors import AppError
from app.repositories.database import get_db
from app.repositories.models import AppUser, AuthSession
from app.services.auth import COOKIE_NAME, token_hash


Database = Annotated[Session, Depends(get_db)]


def require_trusted_origin(request: Request):
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().allowed_origins:
        raise AppError(403, "ORIGIN_FORBIDDEN", "请求来源不被允许")


def current_user(request: Request, db: Database) -> AppUser:
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 128:
        raise AppError(401, "AUTH_REQUIRED", "请先登录")
    row = db.execute(
        select(AuthSession, AppUser).join(AppUser, AppUser.id == AuthSession.user_id).where(
            AuthSession.token_hash == token_hash(token),
            AuthSession.expires_at > datetime.now(timezone.utc), AppUser.active.is_(True),
        )
    ).first()
    if not row:
        raise AppError(401, "AUTH_REQUIRED", "登录已过期，请重新登录")
    auth_session, user = row
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_trusted_origin(request)
        csrf = request.headers.get("x-csrf-token", "")
        if not csrf or len(csrf) > 128 or not secrets.compare_digest(token_hash(csrf), auth_session.csrf_hash):
            raise AppError(403, "CSRF_FAILED", "请求校验失败，请重新登录")
    request.state.auth_session_id = auth_session.id
    return user


CurrentUser = Annotated[AppUser, Depends(current_user)]


def business_user(user: CurrentUser) -> AppUser:
    if user.role != Role.BUSINESS:
        raise AppError(403, "ROLE_FORBIDDEN", "当前账号没有工单处理权限")
    return user


BusinessUser = Annotated[AppUser, Depends(business_user)]
