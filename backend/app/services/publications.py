from collections import Counter

from sqlalchemy import func, select, text

from app.api.publication_schemas import ExperienceHint, PublicationView
from app.domain.enums import TicketStatus
from app.domain.errors import AppError
from app.knowledge.text import bm25_scores, tokenize
from app.repositories.models import AuditEvent, Experience, ExperiencePublication, Ticket
from app.services.tickets import digest, reserve_request
from app.tools.redaction import redact


def publication_view(row):
    return PublicationView(id=row.id, experience_id=row.experience_id, revision=row.revision, status=row.status,
        conditions=row.scope_json, note=row.note, withdrawal_note=row.withdrawal_note, created_at=row.created_at)


def change_publication(db, actor, experience_id, body, *, withdraw_revision=None):
    operation = "experiences.publish" if withdraw_revision is None else "experiences.withdraw"
    payload = {**body.model_dump(mode="json"), "publication_revision": withdraw_revision}
    record, replay = reserve_request(db, actor.id, f"{operation}:{experience_id}", str(body.action_id), payload)
    if replay:
        return record.response_ref
    candidate = db.scalar(select(Experience).where(Experience.id == experience_id).with_for_update())
    if candidate is None:
        raise AppError(404, "EXPERIENCE_NOT_FOUND", "经验候选不存在")
    rows = select(ExperiencePublication).where(ExperiencePublication.experience_id == experience_id)
    active = db.scalar(rows.where(ExperiencePublication.status == "active"))
    reason = redact(body.reason)
    if withdraw_revision is not None:
        if active is None or active.revision != withdraw_revision:
            raise AppError(409, "VERSION_CONFLICT", "当前发布版本已变化")
        row = active
        row.status, row.withdrawal_note = "withdrawn", reason
    else:
        content = candidate.content_json
        if candidate.status != "reviewed" or db.get(Ticket, candidate.source_ticket_id).status != TicketStatus.RESOLVED:
            raise AppError(409, "EXPERIENCE_REVIEW_REQUIRED", "请先审阅已确认解决的经验")
        conditions = content["conditions"]
        if (not content["verified_steps"].strip()
                or any(not conditions.get(key) for key in ("product_ref", "firmware_version"))
                or any(value == "*" for value in conditions.values())):
            raise AppError(422, "EXPERIENCE_SCOPE_REQUIRED", "发布需要已核验措施、明确型号和固件版本")
        if active:
            raise AppError(409, "EXPERIENCE_ALREADY_PUBLISHED", "请先撤回当前发布版本")
        problem_key = digest({"problem": "".join(content["problem"].casefold().split()),
                              "product_ref": conditions["product_ref"], "firmware_version": conditions["firmware_version"]})
        # 跨候选的同范围同问题发布串行，保留一个活动结论给人工复核。
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 9))"), {"key": problem_key})
        same_problem = db.scalars(select(ExperiencePublication.scope_json).where(
            ExperiencePublication.problem_key == problem_key, ExperiencePublication.status == "active"))
        if any(all(conditions[key] == existing[key] for key in conditions.keys() & existing.keys()) for existing in same_problem):
            raise AppError(409, "EXPERIENCE_OVERLAP", "同范围的问题已有发布案例，请先核对措施是否冲突")
        latest = db.scalar(rows.with_only_columns(func.max(ExperiencePublication.revision))) or 0
        row = ExperiencePublication(experience_id=experience_id, revision=latest + 1, status="active",
            problem_key=problem_key, scope_json=conditions, content_json={
                "problem": content["problem"], "verified_steps": content["verified_steps"],
                "source_ticket_id": str(candidate.source_ticket_id),
                "source_run_id": str(candidate.source_run_id) if candidate.source_run_id else None,
                "evidence_refs": content["evidence_refs"], "result_version": candidate.result_version,
            }, note=reason)
        db.add(row)
        db.flush()
    result = publication_view(row).model_dump(mode="json")
    record.response_ref = result
    db.add(AuditEvent(action_id=body.action_id, actor_id=actor.id, ticket_id=candidate.source_ticket_id,
        operation=operation, patch={"reason": reason, "experience_id": str(candidate.id)}, result=result))
    db.commit()
    return result


def recall(db, query):
    scope = query.model_dump(exclude={"query"})
    rows = db.scalars(select(ExperiencePublication).join(Experience).where(
        ExperiencePublication.status == "active", Experience.status == "reviewed",
        ExperiencePublication.scope_json["product_ref"].astext == query.product_ref,
        ExperiencePublication.scope_json["firmware_version"].astext == query.firmware_version,
    ))
    eligible = {str(row.id): row for row in rows if all(scope.get(key) == value for key, value in row.scope_json.items())}
    corpus = {}
    for identifier, row in eligible.items():
        terms = tokenize(row.content_json["problem"])
        if terms:
            corpus[identifier] = {"tf": dict(Counter(terms)), "length": len(terms)}
    return [
        ExperienceHint(publication_id=row.id, revision=row.revision, source_ticket_id=row.content_json["source_ticket_id"],
                       problem=row.content_json["problem"], verified_steps=row.content_json["verified_steps"], conditions=row.scope_json)
        for identifier, _ in bm25_scores(corpus, query.query)[:5] if (row := eligible.get(identifier)) is not None
    ]
