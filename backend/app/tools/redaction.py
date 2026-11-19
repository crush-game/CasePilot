import re


def redact(text: str, *, limit: int | None = 12000) -> str:
    """进入证据和模型前的基础脱敏；样例仅用于契约测试。"""
    text = re.sub(r"(?im)\b(authorization|cookie|set-cookie)\s*[:=][^\r\n]*", r"\1: [REDACTED]", text)
    text = re.sub(r"(?i)\b(bearer)\s+[A-Za-z0-9._~+/-]+", r"\1 [REDACTED]", text)
    text = re.sub(r'''(?i)(["']?\b(?:password|token|api_key|secret)["']?\s*[:=]\s*)(["'][^"']*["']|[^\s,;}]+)''',
                  r"\1[REDACTED]", text)
    result = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[EMAIL]", text)
    return result if limit is None else result[:limit]
