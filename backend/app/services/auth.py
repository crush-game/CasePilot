import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.errors import AppError
from app.repositories.models import AppUser, AuthSession


COOKIE_NAME = "casepilot_session"
COOKIE_PATH = "/api/v1"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode(), salt=bytes.fromhex(salt), n=32768, r=8, p=1, maxmem=64 * 1024 * 1024,
    )
    return f"scrypt$32768$8$1${salt}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        method, n, r, p, salt, expected = encoded.split("$")
        if (method, n, r, p) != ("scrypt", "32768", "8", "1"):
            return False
        actual = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p),
            maxmem=64 * 1024 * 1024,
        ).hex()
        return secrets.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


# 不存在的账号也进行相同的密码运算，不把账号存在性直接暴露为快路径。
DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


def login(db: Session, login_name: str, password: str, old_token: str | None):
    user = db.scalar(select(AppUser).where(AppUser.login == login_name))
    valid = verify_password(password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not valid or not user.active:
        raise AppError(401, "INVALID_CREDENTIALS", "账号或密码错误")
    if old_token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(old_token)))
    token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    db.add(AuthSession(
        user_id=user.id, token_hash=token_hash(token), csrf_hash=token_hash(csrf),
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=get_settings().session_ttl_seconds),
    ))
    db.commit()
    return user, token, csrf
