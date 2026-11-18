import secrets

import pytest
from pydantic import ValidationError

from app.api.schemas import TicketCreate
from app.domain.enums import TicketStatus
from app.domain.errors import AppError
from app.domain.states import require_transition
from app.services.auth import hash_password, verify_password


def test_password_hash_is_salted_and_detects_wrong_password():
    password = secrets.token_urlsafe(24)
    first, second = hash_password(password), hash_password(password)
    assert first != second
    assert password not in first
    assert verify_password(password, first)
    assert not verify_password(password + "wrong", first)


def test_terminal_ticket_cannot_be_silently_reopened():
    require_transition(TicketStatus.QUEUED, TicketStatus.RUNNING)
    with pytest.raises(AppError):
        require_transition(TicketStatus.RESOLVED, TicketStatus.QUEUED)


def test_customer_time_requires_timezone_and_preserves_offset():
    base = {"feedback_text": "设备断连", "customer_email": "demo@example.test"}
    with pytest.raises(ValidationError):
        TicketCreate(**base, occurred_at="2026-11-18T10:00:00")
    parsed = TicketCreate(**base, occurred_at="2026-11-18T10:00:00+08:00")
    assert parsed.occurred_at.isoformat().endswith("+08:00")
