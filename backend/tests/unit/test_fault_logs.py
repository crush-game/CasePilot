from io import BytesIO
import json
import stat
import zipfile

import pytest

from app.faults.logs import MAX_FILE, archive_bytes, parse_log
from app.providers.ledger import ProviderFailure


ROW = {"occurred_at": "2026-11-20T10:00:00+08:00", "domain": "wifi", "text": "disconnect\nAuthorization: Bearer PRIVATE_SAMPLE\npassword=PRIVATE_SAMPLE"}


def test_mock_archive_checksum_is_independent_of_download_time(monkeypatch):
    monkeypatch.setattr(zipfile.time, "localtime", lambda _: (2026, 1, 1, 1, 0, 0, 0, 0, 0))
    first = archive_bytes([{"name": "x.log", "records": [ROW]}])
    monkeypatch.setattr(zipfile.time, "localtime", lambda _: (2026, 1, 1, 2, 0, 0, 0, 0, 0))
    assert first == archive_bytes([{"name": "x.log", "records": [ROW]}])


def test_zip_and_text_keep_line_time_source_and_redact_before_evidence():
    raw = archive_bytes([{"name": "device/events.jsonl", "records": [ROW]}])
    value = parse_log(raw, "application/zip")[0]
    assert value["member_name"] == "device/events.jsonl" and value["line_number"] == 1
    assert value["occurred_at"].utcoffset().total_seconds() == 28800
    assert "PRIVATE_SAMPLE" not in value["text"] and "disconnect" in value["text"]
    assert parse_log(("\ufeff" + json.dumps(ROW)).encode(), "text/plain")[0]["text"] == value["text"]


@pytest.mark.parametrize("name", ["../escape.log", "/root.log", "C:/root.log", "a\\b.log", "code.py"])
def test_archive_path_and_format_escape_is_rejected(name):
    raw = archive_bytes([{"name": name.replace("\\", "/"), "records": [ROW]}])
    if "\\" in name:
        # Windows ZipInfo在写入时会标准化反斜杠，构造原始头部才能覆盖读入边界。
        raw = raw.replace(name.replace("\\", "/").encode(), name.encode())
    with pytest.raises(ProviderFailure, match="UNSAFE_ARCHIVE"):
        parse_log(raw, "application/zip")


def test_symlink_and_duplicate_names_are_rejected():
    raw = BytesIO()
    with zipfile.ZipFile(raw, "w") as archive:
        info = zipfile.ZipInfo("link.log")
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(info, "elsewhere")
    with pytest.raises(ProviderFailure, match="UNSAFE_ARCHIVE"):
        parse_log(raw.getvalue(), "application/zip")
    with pytest.warns(UserWarning):
        raw = archive_bytes([{"name": "x.log", "records": [ROW]}] * 2)
    with pytest.raises(ProviderFailure, match="UNSAFE_ARCHIVE"):
        parse_log(raw, "application/zip")


@pytest.mark.parametrize("files", [[{"name": f"{number}.log", "records": [ROW]} for number in range(11)],
    [{"name": "huge.log", "text": "a" * (MAX_FILE + 1)}]])
def test_file_count_size_and_decompression_bomb_are_bounded(files):
    with pytest.raises(ProviderFailure, match="LOG_LIMIT_EXCEEDED"):
        parse_log(archive_bytes(files), "application/zip")


@pytest.mark.parametrize("raw", [b"not json", b"\xff", json.dumps({**ROW, "occurred_at": "2026-11-20T10:00:00"}).encode()])
def test_malformed_utf8_and_timezone_are_explicit_failures(raw):
    with pytest.raises(ProviderFailure, match="PARSE_FAILED"):
        parse_log(raw, "text/plain")
