"""按北京时间统计已留存的客服事件，并持久化周报及投递。"""

from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.errors import AppError
from app.repositories.database import get_engine
from app.repositories.models import (
    QualityAssessment, QualitySnapshot, SupportConversation, SupportTurn, Ticket, TicketEvent,
    WeeklyDelivery, WeeklyReport,
)
from app.services.calendar import BEIJING
from app.services.quality_scoring import RULES
from app.services.support import WIFI_SYMPTOM


DEFINITION_VERSION = "web-week-v1"
HANDOFF_EVENTS = {"run.paused", "human.claimed"}
QUEUE_END_EVENTS = {"run.started", "run.completed", "run.reinvestigation_queued",
                    "human.resume_queued", "ticket.closed"}


def previous_week(now):
    local = now.astimezone(BEIJING)
    return local.date() - timedelta(days=local.weekday() + 7)


def week_bounds(week):
    start = datetime.combine(week, time.min, BEIJING)
    return start, start + timedelta(days=7)


def summarize(db, week, observed_at):
    start, end = week_bounds(week)
    last = min(end, observed_at)
    support = SupportConversation.flow_version == "support-v2"
    cohort = dict(db.execute(select(SupportConversation.id, SupportConversation.ticket_id).where(
        support, SupportConversation.created_at >= start, SupportConversation.created_at < last)).all())
    opened, confirmed, handed_off = set(), set(), set()
    turns = db.execute(select(SupportTurn.conversation_id, SupportTurn.request_action, SupportTurn.reply_json).where(
        SupportTurn.conversation_id.in_(cohort), SupportTurn.created_at <= observed_at))
    for conversation_id, action, reply in turns:
        if action == "message":
            opened.add(conversation_id)
        if action == "solved" and reply.get("kind") == "feedback":
            confirmed.add(conversation_id)
        if reply.get("kind") == "handoff":
            handed_off.add(conversation_id)

    by_ticket = {ticket_id: key for key, ticket_id in cohort.items() if ticket_id}
    waiting = set()
    events = db.execute(select(TicketEvent.ticket_id, TicketEvent.event_type, TicketEvent.payload_json,
        TicketEvent.created_at).join(SupportConversation, SupportConversation.ticket_id == TicketEvent.ticket_id)
        .where(support, TicketEvent.created_at <= observed_at,
               TicketEvent.event_type.in_(HANDOFF_EVENTS | QUEUE_END_EVENTS | {"ticket.created"}))
        .order_by(TicketEvent.id))
    for ticket_id, kind, data, occurred in events:
        sent_to_human = kind in HANDOFF_EVENTS or (kind == "ticket.created" and data.get("status") == "WAITING_HUMAN")
        if sent_to_human:
            if ticket_id in by_ticket:
                handed_off.add(by_ticket[ticket_id])
            if occurred < last:
                waiting.add(ticket_id)
        elif kind in QUEUE_END_EVENTS and occurred < last:
            waiting.discard(ticket_id)

    ticket_texts = list(db.scalars(select(Ticket.feedback_text).join(SupportConversation)
        .where(support, Ticket.created_at >= start, Ticket.created_at < last)))
    wifi = sum(bool(WIFI_SYMPTOM.search(item)) for item in ticket_texts)
    coverage, deductions = quality_summary(db, start, last, observed_at)
    return {
        "conversations": len(opened),
        "self_resolved": {"count": len((confirmed - handed_off) & opened), "total": len(opened)},
        "handoff": {"count": len(handed_off & opened), "total": len(opened)},
        "new_tickets": len(ticket_texts),
        "pending_human_at_cutoff": len(waiting),
        "faults": {"wifi": wifi, "other": len(ticket_texts) - wifi},
        "quality": coverage,
        "deductions": deductions,
    }


def quality_summary(db, start, end, observed_at):
    snapshots = list(db.scalars(select(QualitySnapshot).where(QualitySnapshot.created_at >= start,
                                                               QualitySnapshot.created_at < end)))
    grouped = defaultdict(list)
    assessments = db.scalars(select(QualityAssessment).join(QualitySnapshot).where(
        QualityAssessment.snapshot_id.in_([row.id for row in snapshots]), QualityAssessment.created_at <= observed_at,
        QualityAssessment.rule_version == QualitySnapshot.rule_version))
    for row in assessments:
        grouped[row.snapshot_id].append(row)
    result = {"total": len(snapshots), "insufficient": 0, "screened": 0, "ai_checked": 0, "reviewed": 0}
    deductions = Counter()
    for snapshot in snapshots:
        rows = grouped[snapshot.id]
        if snapshot.data_json["missing"] or any(row.result_json.get("missing") for row in rows):
            result["insufficient"] += 1
        if rows and all(row.result_json.get("stage") in {"screened", "ai"} for row in rows):
            result["screened"] += 1
        if rows and all(row.result_json.get("stage") == "ai" for row in rows):
            result["ai_checked"] += 1
        if rows and all(row.status == "finalized" for row in rows):
            result["reviewed"] += 1
        for row in rows:
            if row.status == "finalized":
                deductions.update({finding["rule_id"] for finding in row.result_json["findings"]})
    return result, [{"rule_id": rule, "label": RULES[rule][1], "count": count}
                    for rule, count in sorted(deductions.items(), key=lambda item: (-item[1], item[0]))]


def view(db, report):
    deliveries = list(db.scalars(select(WeeklyDelivery).where(WeeklyDelivery.report_id == report.id)
                                  .order_by(WeeklyDelivery.created_at, WeeklyDelivery.id)))
    return {"id": report.id, "week_start": report.week_start, "revision": report.revision,
            "definition_version": report.definition_version, "observed_at": report.observed_at,
            "metrics_json": report.metrics_json, "deliveries": deliveries}


def report_for(db, report_id):
    report = db.get(WeeklyReport, report_id)
    if report is None:
        raise AppError(404, "WEEKLY_REPORT_NOT_FOUND", "周报不存在")
    return report


def generate(db, week: date | None = None, *, now=None, schedule=False):
    now = now or db.scalar(select(func.clock_timestamp()))
    week = week or previous_week(now)
    if week.weekday() != 0 or week > now.astimezone(BEIJING).date():
        raise AppError(422, "WEEK_START_INVALID", "请选择已开始的周一")
    db.execute(select(func.pg_advisory_xact_lock(671901018, week.toordinal())))
    previous = db.scalar(select(WeeklyReport).where(WeeklyReport.week_start == week)
                         .order_by(WeeklyReport.revision.desc()).limit(1))
    if schedule and previous:
        return previous
    with Session(db.get_bind().execution_options(isolation_level="REPEATABLE READ")) as source:
        metrics = summarize(source, week, now)
    if previous and previous.definition_version == DEFINITION_VERSION and previous.metrics_json == metrics:
        return previous
    row = WeeklyReport(week_start=week, revision=previous.revision + 1 if previous else 1,
                       observed_at=now, definition_version=DEFINITION_VERSION, metrics_json=metrics)
    db.add(row)
    db.flush()
    return row


def enqueue(db, report):
    settings = get_settings()
    db.execute(select(func.pg_advisory_xact_lock(671901018, report.week_start.toordinal())))
    mode = "feishu" if settings.weekly_report_webhook else "mock"
    key = db.scalar(insert(WeeklyDelivery).values(report_id=report.id, group_key=settings.weekly_report_group,
        mode=mode).on_conflict_do_nothing(constraint="uq_weekly_deliveries_report_group").returning(WeeklyDelivery.id))
    if key:
        return db.get(WeeklyDelivery, key)
    return db.scalar(select(WeeklyDelivery).where(WeeklyDelivery.report_id == report.id,
                                                  WeeklyDelivery.group_key == settings.weekly_report_group))


def schedule_once(now=None):
    if not get_settings().weekly_report_enabled:
        return False
    with Session(get_engine()) as db:
        now = now or db.scalar(select(func.clock_timestamp()))
        local = now.astimezone(BEIJING)
        if local.weekday() == 0 and local.time() < time(9):
            return False
        report = generate(db, now=now, schedule=True)
        queued = db.scalar(select(WeeklyDelivery.id).join(WeeklyReport).where(
            WeeklyReport.week_start == report.week_start,
            WeeklyDelivery.group_key == get_settings().weekly_report_group).limit(1))
        if queued:
            return False
        enqueue(db, report)
        db.commit()
        return True


def notification(report, origin):
    value = report.metrics_json
    handoff = value["handoff"]
    solution = value["self_resolved"]
    quality = value["quality"]
    lines = [
        f"CasePilot 售后周报 {report.week_start}（第 {report.revision} 版）",
        f"客服会话 {value['conversations']}，新增工单 {value['new_tickets']}，待人工 {value['pending_human_at_cutoff']}",
        f"确认自助解决 {solution['count']}/{solution['total']}，转人工 {handoff['count']}/{handoff['total']}",
        f"结案快照 {quality['total']}，初筛 {quality['screened']}，精检 {quality['ai_checked']}，复核 {quality['reviewed']}",
        f"查看面板 {origin}/reports?report_id={report.id}",
    ]
    return "\n".join(lines)


def send_notification(mode, group_key, text):
    if mode == "mock":
        return "sent", "MOCK_RECEIPT"
    settings = get_settings()
    if not settings.weekly_report_webhook or settings.weekly_report_group != group_key:
        return "failed", "DESTINATION_UNAVAILABLE"
    try:
        result = httpx.post(settings.weekly_report_webhook.get_secret_value(),
                            json={"msg_type": "text", "content": {"text": text}}, timeout=5.0)
    except (httpx.ConnectTimeout, httpx.ConnectError):
        return "retry", "CONNECT_FAILED"
    except httpx.RequestError:
        return "unknown", "RESPONSE_UNCONFIRMED"
    if result.status_code == 429:
        return "retry", "RATE_LIMITED"
    if result.status_code >= 500:
        return "unknown", "SERVER_RESPONSE_UNCONFIRMED"
    if result.status_code != 200:
        return "failed", "HTTP_REJECTED"
    try:
        payload = result.json()
        code = payload.get("code", payload.get("StatusCode"))
    except (ValueError, AttributeError):
        return "unknown", "RESPONSE_UNCONFIRMED"
    if code == 0:
        return "sent", "FEISHU_ACCEPTED"
    if code == 11232:
        return "retry", "RATE_LIMITED"
    return ("unknown", "RESPONSE_UNCONFIRMED") if code is None else ("failed", "FEISHU_REJECTED")


def deliver_once(delivery_id=None, *, sender=send_notification):
    with Session(get_engine()) as db:
        now = db.scalar(select(func.clock_timestamp()))
        query = select(WeeklyDelivery).order_by(WeeklyDelivery.available_at, WeeklyDelivery.id).limit(1)
        if delivery_id:
            query = query.where(WeeklyDelivery.id == delivery_id)
        expired = db.scalar(query.where(WeeklyDelivery.status == "sending",
            WeeklyDelivery.started_at < now - timedelta(seconds=30)).with_for_update(skip_locked=True))
        if expired:
            expired.status, expired.receipt = "unknown", "WORKER_RESPONSE_LOST"
            db.commit()
            return True
        row = db.scalar(query.where(WeeklyDelivery.status == "queued",
                                   WeeklyDelivery.available_at <= now).with_for_update(skip_locked=True))
        if row is None:
            return False
        row.status, row.started_at, row.attempts = "sending", now, row.attempts + 1
        key, attempt, mode, group = row.id, row.attempts, row.mode, row.group_key
        text = notification(db.get(WeeklyReport, row.report_id), get_settings().weekly_report_origin)
        db.commit()
    status, receipt = sender(mode, group, text)
    with Session(get_engine()) as db:
        row = db.scalar(select(WeeklyDelivery).where(WeeklyDelivery.id == key).with_for_update())
        if row.status != "sending" or row.attempts != attempt:
            return True
        row.receipt = receipt
        if status == "retry" and attempt < 3:
            row.status = "queued"
            row.available_at = db.scalar(select(func.clock_timestamp())) + timedelta(seconds=2 ** attempt)
        else:
            row.status = "failed" if status == "retry" else status
        db.commit()
    return True
