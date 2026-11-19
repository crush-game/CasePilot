from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
import unicodedata

from app.tools.redaction import redact


TOKENIZER = "zh-bigram-v1"
MAX_FILE_BYTES = 1024 * 1024
MAX_CHUNKS = 2000


class IngestionFailure(Exception):
    def __init__(self, code, retryable=False):
        self.code, self.retryable = code, retryable
        super().__init__(code)


def checksum(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tokenize(text: str) -> list[str]:
    # 小规模原型不引入词典：汉字单字＋相邻二元词项；型号/错误码保持完整词项。
    text = unicodedata.normalize("NFKC", text).casefold()
    terms = []
    for match in re.finditer(r"[a-z0-9]+(?:[._-][a-z0-9]+)*|[\u3400-\u9fff]+", text):
        value = match.group()
        if re.fullmatch(r"[\u3400-\u9fff]+", value):
            terms.extend(value)
            terms.extend(value[i:i + 2] for i in range(len(value) - 1))
        else:
            terms.append(value)
    return terms


@dataclass(frozen=True)
class ParsedChunk:
    text: str
    heading_path: list[str]
    start_line: int
    end_line: int
    parent_start_line: int
    parent_end_line: int


def split_document(raw: bytes, filename: str) -> list[ParsedChunk]:
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise IngestionFailure("EMPTY_FILE" if not raw else "FILE_TOO_LARGE")
    try:
        text = raw.decode("utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        raise IngestionFailure("INVALID_UTF8") from None
    if any(ord(char) < 32 and char not in "\n\t" for char in text):
        raise IngestionFailure("INVALID_TEXT")
    lines = text.splitlines()
    if any(len(line) > 4096 for line in lines):
        raise IngestionFailure("LINE_TOO_LONG")
    if not text.strip():
        raise IngestionFailure("EMPTY_DOCUMENT")
    lines = [redact(line) for line in lines]
    sections, headings, current, start_line, fence = [], [], [], 1, None
    markdown = filename.lower().endswith(".md")
    for number, line in enumerate(lines, 1):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line) if markdown else None
        heading = re.match(r"^ {0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line) if markdown and fence is None else None
        if heading:
            if current:
                sections.append((current, [title for _, title in headings], start_line))
            level = len(heading[1])
            headings = [*(value for value in headings if value[0] < level), (level, heading[2])]
            current, start_line = [], number
        if marker:
            if fence is None:
                fence = marker[1]
            elif re.fullmatch(r"\s*" + re.escape(fence[0]) + "{" + str(len(fence)) + r",}\s*", line):
                fence = None
        current.append(line)
    if current:
        sections.append((current, [title for _, title in headings], start_line))
    chunks = []
    for rows, path, base in sections:
        body, offset = "\n".join(rows), 0
        while offset < len(body):
            end = min(offset + 1000, len(body))
            if end < len(body):
                boundary = body.rfind("\n\n", offset + 600, end)
                if boundary < 0:
                    boundary = body.rfind("\n", offset + 600, end)
                if boundary < 0:
                    boundary = max(body.rfind(char, offset + 600, end) for char in "。！？；")
                if boundary >= 0:
                    end = boundary + 1
            part = body[offset:end]
            if part.strip():
                chunks.append(ParsedChunk(part, path, base + body.count("\n", 0, offset),
                    base + body.count("\n", 0, end - 1), base, base + len(rows) - 1))
            if end == len(body):
                break
            offset = end - 100
    if not chunks or not any(tokenize(chunk.text) for chunk in chunks):
        raise IngestionFailure("EMPTY_DOCUMENT")
    if len(chunks) > MAX_CHUNKS:
        raise IngestionFailure("TOO_MANY_CHUNKS")
    return chunks


def bm25_scores(documents: dict[str, dict], query: str) -> list[tuple[str, float]]:
    terms = set(tokenize(query))
    if not terms or not documents:
        return []
    n = len(documents)
    average = sum(row["length"] for row in documents.values()) / n
    frequencies = Counter(term for row in documents.values() for term in row["tf"])
    scored = []
    for ref, row in documents.items():
        score = 0.0
        for term in terms:
            tf = row["tf"].get(term, 0)
            if tf:
                # 正值 IDF 的 BM25 变体；固定 k1=1.2、b=0.75，分数不代表置信度。
                idf = math.log1p((n - frequencies[term] + 0.5) / (frequencies[term] + 0.5))
                score += idf * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * row["length"] / average))
        if score > 0:
            scored.append((ref, score))
    return sorted(scored, key=lambda row: (-row[1], row[0]))
