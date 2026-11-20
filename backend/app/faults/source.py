"""只读、带版本的公开企业数据样例。真实后台接口未授权，不提供隐式生产回落。"""

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re

from app.providers.ledger import ProviderFailure
from app.services.tickets import digest


FIXTURE_ROOT = Path(__file__).resolve().parents[3] / "fixtures/enterprise"
CONTEXT_FIELDS = ("device_ref", "product_ref", "firmware_version", "platform", "app_version", "occurred_at")


def source_path(key):
    if not re.fullmatch(r"[a-z0-9_-]{1,80}", key):
        raise ProviderFailure("ENTERPRISE_SOURCE_NOT_CONFIGURED")
    path = (FIXTURE_ROOT / (key + ".json")).resolve()
    if path.parent != FIXTURE_ROOT.resolve():
        raise ProviderFailure("ENTERPRISE_SOURCE_NOT_CONFIGURED")
    return path


def source_snapshot(key):
    try:
        raw = source_path(key).read_bytes()
        if len(raw) > 4 * 1024 * 1024:
            raise ValueError()
        data = json.loads(raw)
        if data.get("data_source") != "mock":
            raise ValueError()
    except (OSError, ValueError):
        raise ProviderFailure("ENTERPRISE_SOURCE_NOT_CONFIGURED") from None
    return {"provider": "mock", "fixture_key": key, "checksum": hashlib.sha256(raw).hexdigest()}


def load_source(config):
    if config.get("provider") != "mock":
        raise ProviderFailure("ENTERPRISE_PROVIDER_NOT_AUTHORIZED")
    path = source_path(config["fixture_key"])
    try:
        raw = path.read_bytes()
        if len(raw) > 4 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != config["checksum"]:
            raise ProviderFailure("ENTERPRISE_SOURCE_CHANGED")
        data = json.loads(raw)
        if data.get("data_source") != "mock":
            raise ValueError()
        return data
    except (OSError, ValueError):
        raise ProviderFailure("ENTERPRISE_SOURCE_UNAVAILABLE") from None


def context_hash(ticket_id, request):
    return digest({"ticket_id": str(ticket_id), **{field: request.get(field) for field in CONTEXT_FIELDS}})


def timestamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("时间必须带时区")
    return parsed


def feedbacks(data, email, request):
    owned = [row for row in data.get("feedbacks", []) if row.get("customer_email") == email]
    if not owned:
        return [], "NO_FEEDBACK"
    rows = []
    for row in owned:
        if any(request.get(field) and row.get(field) != request[field] for field in CONTEXT_FIELDS if field != "occurred_at"):
            continue
        if request.get("occurred_at"):
            try:
                if abs((timestamp(row["occurred_at"]) - timestamp(request["occurred_at"])).total_seconds()) > 1800:
                    continue
            except (ValueError, KeyError, TypeError):
                continue
        rows.append(row)
    return sorted(rows, key=lambda row: (row["occurred_at"], row["record_id"])), None if rows else "NO_MATCHING_RECORD"


def require_feedback(config, email, request, ref):
    data = load_source(config)
    rows, _ = feedbacks(data, email, request)
    row = next((row for row in rows if row["record_id"] == ref), None)
    if row is None:
        raise ProviderFailure("FEEDBACK_SCOPE_MISMATCH")
    return data, row
