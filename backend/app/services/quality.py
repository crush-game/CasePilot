"""结案快照和质检任务。后台默认处理本地模拟文本。"""

import hashlib
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.errors import AppError
from app.repositories.database import get_engine
from app.repositories.models import (
    AppUser, QualityAssessment, QualityBatch, QualityRuleSet, QualitySnapshot, SupportConversation,
    SupportDelivery, SupportTurn, TicketFact,
)
from app.services import quality_scoring as scoring
from app.services.tickets import get_ticket, reserve_request
from app.services.workflow_common import append_event
from app.tools.redaction import redact


DEFAULT_RULE_VERSION = "v0.1"


def lock_close_conversation(db, ticket):
    if ticket.source != "app_support":
        return None
    row = db.scalar(select(SupportConversation).where(SupportConversation.ticket_id == ticket.id,
                                                      SupportConversation.flow_version == "support-v2"))
    if row and db.scalar(select(SupportDelivery.id).where(SupportDelivery.conversation_id == row.id,
            SupportDelivery.status == "queued").limit(1)):
        raise AppError(409, "SUPPORT_REPLY_PENDING", "有正式回复等待投递，请在送达后结案")
    return row


def freeze(db, ticket, conversation):
    turns = list(db.scalars(select(SupportTurn).where(SupportTurn.conversation_id == conversation.id)
                            .order_by(SupportTurn.id)))
    delivered = {row.provider_ref: row.reply_author_id for row in db.scalars(
        select(SupportDelivery).where(SupportDelivery.conversation_id == conversation.id,
                                      SupportDelivery.channel == "app", SupportDelivery.status == "delivered"))}
    messages = []
    subjects = set()
    missing = set()
    for turn in turns:
        stamp = turn.created_at.isoformat()
        if turn.request_text and turn.request_text not in {"转人工", "补充设备信息", "提交设备故障", "回答已解决问题"}:
            messages.append({"id": f"message:{turn.id}", "role": "customer",
                             "text": redact(turn.request_text), "at": stamp})
        if turn.reply_json["kind"] == "agent_reply":
            author = delivered.get(f"app:{turn.id}")
            if author:
                subjects.add(author)
            else:
                missing.add("存在作者未确认的人工回复")
            messages.append({"id": f"reply:{turn.id}", "role": "human", "author": str(author) if author else None,
                             "text": redact(turn.reply_json["text"]), "at": stamp})
        elif turn.reply_json["kind"] == "answer":
            messages.append({"id": f"reply:{turn.id}", "role": "assistant",
                             "text": redact(turn.reply_json["text"]), "at": stamp})
    if not subjects:
        missing.add("缺少带作者的已送达人工回复")
    facts = {}
    for fact in db.scalars(select(TicketFact).where(TicketFact.ticket_id == ticket.id, TicketFact.field == "product_ref")
                           .order_by(TicketFact.fact_version, TicketFact.id)):
        facts[fact.field] = redact(str(fact.value_json["value"]))
    calendar = get_settings().service_calendar
    data = {"messages": messages, "facts": facts, "missing": sorted(missing),
            "assignee": str(ticket.assignee_id) if ticket.assignee_id else None,
            "closure": {"outcome": ticket.result_json["outcome"], "reason": redact(ticket.result_json["reason"])},
            "calendar": calendar.model_dump(mode="json") if calendar else None}
    snapshot = QualitySnapshot(ticket_id=ticket.id, conversation_id=conversation.id, case_version=ticket.version,
                               rule_version=DEFAULT_RULE_VERSION, data_json=data)
    db.add(snapshot)
    db.flush()
    db.add_all(QualityAssessment(snapshot_id=snapshot.id, subject_id=subject, rule_version=DEFAULT_RULE_VERSION)
               for subject in sorted(subjects))
    append_event(db, ticket, "quality.snapshot_saved", {"snapshot_id": str(snapshot.id), "subjects": len(subjects)})


def assessment_view(row, snapshot, subject, *, detail=False):
    attributes = {"id": row.id, "snapshot_id": snapshot.id, "ticket_id": snapshot.ticket_id,
                  "subject_id": row.subject_id, "subject_name": subject, "rule_version": row.rule_version,
                  "status": row.status, "version": row.version, "result_json": row.result_json,
                  "history_json": row.history_json, "created_at": row.created_at}
    if detail:
        attributes["snapshot"] = snapshot.data_json
    return attributes


def assessment_query():
    return select(QualityAssessment, QualitySnapshot, AppUser.login).join(QualitySnapshot).join(
        AppUser, AppUser.id == QualityAssessment.subject_id)


def list_assessments(db, ticket_id, cursor, limit):
    query = assessment_query().where(QualityAssessment.status != "queued")
    missing = []
    if ticket_id:
        query = query.where(QualitySnapshot.ticket_id == ticket_id)
        snapshot = db.scalar(select(QualitySnapshot).where(QualitySnapshot.ticket_id == ticket_id))
        missing = snapshot.data_json["missing"] if snapshot else []
    if cursor:
        query = query.where(QualityAssessment.id > cursor)
    rows = list(db.execute(query.order_by(QualityAssessment.id).limit(limit + 1)))
    return {"items": [assessment_view(*row) for row in rows[:limit]], "snapshot_missing": missing,
            "next_cursor": rows[limit - 1][0].id if len(rows) > limit else None}


def get_assessment(db, assessment_id):
    result = db.execute(assessment_query().where(QualityAssessment.id == assessment_id)).first()
    if result is None:
        raise AppError(404, "QUALITY_NOT_FOUND", "质检记录不存在")
    return assessment_view(*result, detail=True)


def publish_rules(db, body):
    config = body.model_dump(exclude={"version"})
    key = db.scalar(insert(QualityRuleSet).values(version=body.version, config_json=config)
                    .on_conflict_do_nothing().returning(QualityRuleSet.version))
    if key is None and db.get(QualityRuleSet, body.version).config_json != config:
        raise AppError(409, "QUALITY_RULE_VERSION_EXISTS", "规则版本已经存在")
    db.commit()
    return body


def create_batch(db, body):
    if body.ticket_id:
        get_ticket(db, body.ticket_id)
    key = db.scalar(insert(QualityBatch).values(batch_key=body.batch_key, random_pct=body.random_pct,
        max_calls=body.max_calls, ticket_id=body.ticket_id, selection_json=[]).on_conflict_do_nothing().returning(QualityBatch.id))
    if key is None:
        row = db.scalar(select(QualityBatch).where(QualityBatch.batch_key == body.batch_key))
        if (row.random_pct, row.max_calls, row.ticket_id) != (body.random_pct, body.max_calls, body.ticket_id):
            raise AppError(409, "QUALITY_BATCH_CONFLICT", "同一批次键已经使用其他抽样参数")
        return row
    batch = db.get(QualityBatch, key)
    ready = or_(QualityAssessment.status == "screened", and_(
        QualityAssessment.status == "ai_queued", QualityBatch.calls_used >= QualityBatch.max_calls))
    query = select(QualityAssessment).outerjoin(QualityBatch).where(ready)
    if body.ticket_id:
        query = query.join(QualitySnapshot).where(QualitySnapshot.ticket_id == body.ticket_id)
    candidates = list(db.scalars(query.order_by(QualityAssessment.created_at, QualityAssessment.id)
                                 .with_for_update(of=QualityAssessment, skip_locked=True)))
    selection = []
    for row in candidates:
        risk = bool(row.result_json.get("risk"))
        value = int(hashlib.sha256(f"{body.batch_key}:{row.id}".encode()).hexdigest(), 16) % 100
        if risk or row.status == "ai_queued" or value < body.random_pct:
            reason = "risk" if risk else "carryover" if row.status == "ai_queued" else "sample"
            row.batch_id, row.status = key, "ai_queued"
            selection.append({"assessment_id": str(row.id), "reason": reason})
    batch.selection_json = selection
    db.commit()
    return batch


def process_one(*, assessment_id=None, judge=scoring.mock_judge):
    # 模拟判定没有外部副作用，预算和结果同事务提交，进程中断时一起回滚。
    with Session(get_engine()) as db:
        query = select(QualityAssessment).order_by(QualityAssessment.created_at, QualityAssessment.id).limit(1)
        if assessment_id is not None:
            query = query.where(QualityAssessment.id == assessment_id)
        row = db.scalar(query.where(QualityAssessment.status == "queued").with_for_update(skip_locked=True))
        if row is not None:
            data = db.get(QualitySnapshot, row.snapshot_id).data_json
            config = db.get(QualityRuleSet, row.rule_version).config_json
            notes, missing, risk = scoring.preliminary(data, str(row.subject_id), config)
            row.result_json = {**scoring.score(notes, config, missing=missing), "risk": risk, "stage": "screened"}
            row.status = "insufficient" if missing else "screened"
        else:
            row = db.scalar(query.join(QualityBatch).where(QualityAssessment.status == "ai_queued",
                QualityBatch.calls_used < QualityBatch.max_calls)
                .order_by(None).order_by(QualityAssessment.result_json["risk"].as_boolean().desc(),
                                         QualityAssessment.created_at, QualityAssessment.id)
                .with_for_update(of=QualityAssessment, skip_locked=True))
            if row is None:
                return False
            batch = db.scalar(select(QualityBatch).where(QualityBatch.id == row.batch_id).with_for_update())
            if batch.calls_used >= batch.max_calls:
                return False
            data = db.get(QualitySnapshot, row.snapshot_id).data_json
            config = db.get(QualityRuleSet, row.rule_version).config_json
            findings = row.result_json["findings"]
            missing = []
            batch.calls_used += 1
            try:
                findings = [*findings, *scoring.checked_findings(judge(data, str(row.subject_id)), data,
                                                               str(row.subject_id), semantic_only=True)]
            except (ValueError, KeyError, TypeError):
                missing = ["模拟判定的规则或引用无法核对"]
            row.result_json = {**scoring.score(findings, config, missing=missing),
                               "risk": row.result_json["risk"], "stage": "ai", "usage": {"calls": 1, "tokens": None}}
            row.status = "pending_review"
        row.version += 1
        db.commit()
        return True


def decide(db, actor, assessment_id, body):
    operation = f"quality.decide:{assessment_id}"
    record, replay = reserve_request(db, actor.id, operation, str(body.action_id), body.model_dump(mode="json"))
    if replay:
        return record.response_ref
    row = db.scalar(select(QualityAssessment).where(QualityAssessment.id == assessment_id).with_for_update())
    if row is None:
        raise AppError(404, "QUALITY_NOT_FOUND", "质检记录不存在")
    if row.version != body.expected_version:
        raise AppError(409, "VERSION_CONFLICT", "质检结果已更新，请刷新")
    snapshot = db.get(QualitySnapshot, row.snapshot_id)
    previous = row.result_json
    if body.decision == "appeal":
        if row.subject_id != actor.id:
            raise AppError(403, "QUALITY_SUBJECT_REQUIRED", "只能申诉自己的质检结果")
        if row.status != "finalized":
            raise AppError(409, "INVALID_STATE", "确认后的评分才能申诉")
        row.status = "appealed"
    else:
        if row.subject_id == actor.id:
            raise AppError(403, "QUALITY_REVIEWER_REQUIRED", "请由另一位业务人员复核")
        if body.decision == "rescore":
            if body.rule_version == row.rule_version or db.get(QualityRuleSet, body.rule_version) is None:
                raise AppError(422, "QUALITY_RULE_VERSION_INVALID", "请选择另一已发布版本")
            new_id = db.scalar(insert(QualityAssessment).values(snapshot_id=row.snapshot_id,
                subject_id=row.subject_id, rule_version=body.rule_version).on_conflict_do_nothing(
                    constraint="uq_quality_assessments_subject_rule").returning(QualityAssessment.id))
            result = db.get(QualityAssessment, new_id) if new_id else db.scalar(select(QualityAssessment).where(
                QualityAssessment.snapshot_id == row.snapshot_id, QualityAssessment.subject_id == row.subject_id,
                QualityAssessment.rule_version == body.rule_version))
            row.history_json = [*row.history_json, {"decision": "rescore", "actor_id": str(actor.id),
                "reason": redact(body.reason), "target_id": str(result.id), "rule_version": body.rule_version}]
            row.version += 1
            return finish(db, record, result, snapshot)
        if row.status not in {"screened", "pending_review", "appealed", "insufficient"}:
            raise AppError(409, "INVALID_STATE", "当前质检状态不可复核")
        config = db.get(QualityRuleSet, row.rule_version).config_json
        try:
            findings = (scoring.checked_findings({"findings": [item.model_dump() for item in body.findings]},
                        snapshot.data_json, str(row.subject_id)) if body.findings is not None else row.result_json["findings"])
        except (ValueError, KeyError) as exc:
            raise AppError(422, "QUALITY_EVIDENCE_INVALID", "判定引用不属于此会话或受评客服") from exc
        if row.result_json.get("missing") and body.decision == "confirm":
            raise AppError(409, "QUALITY_EVIDENCE_INCOMPLETE", "请补充人工判定后确认")
        if snapshot.data_json["missing"]:
            raise AppError(409, "QUALITY_SNAPSHOT_INCOMPLETE", "快照有缺失，保留待判定状态")
        row.result_json = {**row.result_json, **scoring.score(findings, config, confirmed=True)}
        row.status = "finalized"
    row.history_json = [*row.history_json, {"decision": body.decision, "actor_id": str(actor.id),
        "reason": redact(body.reason), "previous": previous, "result": row.result_json, "status": row.status}]
    row.version += 1
    return finish(db, record, row, snapshot)


def finish(db, record, row, snapshot):
    from app.api.quality_schemas import QualityDetail

    response = QualityDetail.model_validate(assessment_view(row, snapshot,
                db.get(AppUser, row.subject_id).login, detail=True)).model_dump(mode="json")
    record.response_ref = response
    db.commit()
    return response
