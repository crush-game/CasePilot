"""隔离的声明检索实验。此模块不会进入工作台知识检索或改写文档。"""
from collections import Counter
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.knowledge.text import bm25_scores, tokenize


class Scope(BaseModel):
    entity: str
    firmware: str | None
    as_of: date


class Chunk(BaseModel):
    ref: str
    entity: str
    firmware: str
    text: str
    document_version: int = Field(ge=1)
    source_type: Literal["official", "experience"] = "official"
    status: Literal["active", "draft", "superseded", "withdrawn"] = "active"
    effective_from: date
    effective_to: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("声明片段的有效期必须为正向区间")
        return self


class Claim(BaseModel):
    chunk_ref: str
    field: str
    value: str
    cardinality: Literal["single", "multi"] = "single"
    status: Literal["active", "draft", "withdrawn"] = "active"


class Corpus(BaseModel):
    chunks: list[Chunk]
    claims: list[Claim]
    aliases: dict[str, list[str]]

    @model_validator(mode="after")
    def references(self):
        refs = {chunk.ref for chunk in self.chunks}
        if len(refs) != len(self.chunks) or any(claim.chunk_ref not in refs or claim.field not in self.aliases for claim in self.claims):
            raise ValueError("声明必须引用真实、唯一的片段与属性")
        return self


def applicable(chunk: Chunk, scope: Scope) -> bool:
    return (chunk.status == "active" and chunk.source_type == "official" and chunk.entity == scope.entity
            and (chunk.firmware == "*" or chunk.firmware == scope.firmware)
            and chunk.effective_from <= scope.as_of
            and (chunk.effective_to is None or scope.as_of < chunk.effective_to))


def eligible_chunks(corpus: Corpus, scope: Scope):
    unavailable = {claim.chunk_ref for claim in corpus.claims if claim.status != "active"}
    return [chunk for chunk in corpus.chunks if applicable(chunk, scope) and chunk.ref not in unavailable]


def chunk_search(corpus: Corpus, scope: Scope, question: str, limit: int = 3) -> list[str]:
    indexed = {}
    for chunk in eligible_chunks(corpus, scope):
        terms = tokenize(chunk.text)
        if terms:
            indexed[chunk.ref] = {"tf": dict(Counter(terms)), "length": len(terms)}
    return [ref for ref, _ in bm25_scores(indexed, question)[:limit]]


def claim_search(corpus: Corpus, scope: Scope, question: str, limit: int = 3) -> dict:
    fields = [field for field, names in corpus.aliases.items()
              if any(name.casefold() in question.casefold() for name in names)]
    if len(fields) != 1:
        return {"status": "missing_field", "refs": []}
    field = fields[0]
    refs = {chunk.ref for chunk in eligible_chunks(corpus, scope)}
    found = [claim for claim in corpus.claims if claim.chunk_ref in refs and claim.field == field and claim.status == "active"]
    if not found:
        return {"status": "missing_evidence", "refs": []}
    distinct = {claim.value for claim in found}
    status = "conflict" if len(distinct) > 1 and any(claim.cardinality == "single" for claim in found) else "found"
    # 同值可只取一份出处，冲突必须给出不同值的来源。
    by_value = {}
    for claim in found:
        by_value.setdefault(claim.value, claim.chunk_ref)
    return {"status": status, "refs": list(dict.fromkeys(by_value.values()))[:limit]}
