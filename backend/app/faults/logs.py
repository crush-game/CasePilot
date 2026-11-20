"""有界 ZIP/UTF-8 JSONL 日志解析；不将压缩文件写到磁盘。"""

import hashlib
from io import BytesIO
import json
from pathlib import PurePosixPath
import stat
import zipfile

from app.faults.source import timestamp
from app.providers.ledger import ProviderFailure
from app.tools.redaction import redact


MAX_INPUT = 2 * 1024 * 1024
MAX_FILE = 1024 * 1024
MAX_TOTAL = 4 * 1024 * 1024
MAX_FILES = 10


def archive_bytes(files):
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for entry in files:
            text = entry.get("text")
            if text is None:
                text = "\n".join(json.dumps(row, ensure_ascii=False) for row in entry["records"])
            # Mock附件内容固定，重启时不能因ZIP创建时间改变来源校验和。
            info = zipfile.ZipInfo(entry["name"], date_time=(2026, 1, 1, 0, 0, 0))
            archive.writestr(info, text.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
    return stream.getvalue()


def parse_log(raw, media_type):
    if not raw or len(raw) > MAX_INPUT:
        raise ProviderFailure("LOG_LIMIT_EXCEEDED")
    files = []
    try:
        if media_type == "application/zip":
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                entries = archive.infolist()
                if not 0 < len(entries) <= MAX_FILES:
                    raise ProviderFailure("LOG_LIMIT_EXCEEDED")
                total, names = 0, set()
                for entry in entries:
                    name = entry.orig_filename
                    path = PurePosixPath(name)
                    if (not name or len(name) > 200 or "\\" in name or ":" in name or "\x00" in name
                            or path.is_absolute() or ".." in path.parts or name in names or entry.is_dir()
                            or stat.S_ISLNK(entry.external_attr >> 16) or entry.flag_bits & 1
                            or path.suffix.lower() not in {".txt", ".log", ".jsonl"}):
                        raise ProviderFailure("UNSAFE_ARCHIVE")
                    names.add(name)
                    total += entry.file_size
                    if entry.file_size > MAX_FILE or total > MAX_TOTAL or entry.file_size > max(1, entry.compress_size) * 100:
                        raise ProviderFailure("LOG_LIMIT_EXCEEDED")
                    with archive.open(entry) as source:
                        value = source.read(MAX_FILE + 1)
                    if len(value) > MAX_FILE:
                        raise ProviderFailure("LOG_LIMIT_EXCEEDED")
                    files.append((name, value))
        elif media_type == "text/plain":
            if len(raw) > MAX_FILE:
                raise ProviderFailure("LOG_LIMIT_EXCEEDED")
            files = [("log.jsonl", raw)]
        else:
            raise ProviderFailure("PARSE_FAILED")
        rows = []
        for name, value in files:
            text = value.decode("utf-8-sig")
            if "\x00" in text:
                raise ValueError()
            for number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                if len(line) > 4096 or len(rows) >= 10000:
                    raise ProviderFailure("LOG_LIMIT_EXCEEDED")
                item = json.loads(line)
                domain, message = item["domain"], item["text"]
                if domain not in {"wifi", "ota", "power", "media", "system"} or not isinstance(message, str):
                    raise ValueError()
                sanitized = redact(message, limit=None)
                rows.append({"member_name": name, "line_number": number, "occurred_at": timestamp(item["occurred_at"]),
                             "domain": domain, "text": sanitized, "content_hash": hashlib.sha256(sanitized.encode()).hexdigest()})
        if not rows:
            raise ValueError()
        return rows
    except ProviderFailure:
        raise
    except (zipfile.BadZipFile, UnicodeError, ValueError, KeyError, TypeError, RuntimeError, NotImplementedError):
        raise ProviderFailure("PARSE_FAILED") from None
