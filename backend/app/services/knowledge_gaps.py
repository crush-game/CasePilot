"""质检发现进入人工核对的知识缺口，原始判断留在快照。"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.domain.errors import AppError
from app.repositories.models import KnowledgeGap, QualityAssessment, QualitySnapshot
from app.tools.redaction import redact


def create(db, actor, assessment_id, body):
    row = db.scalar(select(QualityAssessment).where(QualityAssessment.id == assessment_id).with_for_update())
    if row is None:
        raise AppError(404, "QUALITY_NOT_FOUND", "质检记录不存在")
    if row.status != "finalized":
        raise AppError(409, "QUALITY_REVIEW_REQUIRED", "请从已确认的质检发现提交")
    if row.subject_id == actor.id:
        raise AppError(403, "QUALITY_REVIEWER_REQUIRED", "请由其他业务人员提交知识缺口")
    item = next((item for item in row.result_json["findings"] if item["rule_id"] == body.rule_id), None)
    if item is None:
        raise AppError(422, "QUALITY_FINDING_NOT_FOUND", "当前质检记录没有该规则发现")
    snapshot = db.get(QualitySnapshot, row.snapshot_id)
    selected = set(item["evidence"])
    excerpts = [{"ref": message["id"], "role": message["role"], "text": message["text"]}
                for message in snapshot.data_json["messages"] if message["id"] in selected]
    evidence = {"ticket_id": str(snapshot.ticket_id), "snapshot_id": str(snapshot.id),
                "assessment_version": row.version, "refs": item["evidence"], "excerpts": excerpts,
                "statement": redact(body.statement)}
    key = db.scalar(insert(KnowledgeGap).values(assessment_id=row.id, rule_id=body.rule_id, actor_id=actor.id,
        evidence_json=evidence).on_conflict_do_nothing(
            constraint="uq_quality_gaps_assessment_rule").returning(KnowledgeGap.id))
    result = db.get(KnowledgeGap, key) if key else db.scalar(select(KnowledgeGap).where(
        KnowledgeGap.assessment_id == row.id, KnowledgeGap.rule_id == body.rule_id))
    if result.evidence_json["statement"] != evidence["statement"]:
        raise AppError(409, "KNOWLEDGE_GAP_EXISTS", "该质检项已有缺口，保留原始提交")
    db.commit()
    return result


def resolve(db, actor, gap_id, body):
    row = db.scalar(select(KnowledgeGap).where(KnowledgeGap.id == gap_id).with_for_update())
    if row is None:
        raise AppError(404, "KNOWLEDGE_GAP_NOT_FOUND", "知识缺口不存在")
    if row.status != "pending":
        raise AppError(409, "INVALID_STATE", "知识缺口已经处理")
    row.status = body.decision
    row.resolution_json = {"actor_id": str(actor.id), "reason": redact(body.reason)}
    db.commit()
    return row
