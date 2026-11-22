"""编排本地质检规则和模拟语义判定。分数由服务端计算。"""

from collections import defaultdict
from datetime import datetime, timedelta
import re

from app.api.quality_schemas import QualityJudgment
from app.services.calendar import BEIJING, ServiceCalendar


RULES = {
    "fatal_review": ("fatal", "疑似诱导删除差评"),
    "business_incomplete": ("business", "未回答客户提出的问题"),
    "process_late": ("process", "跟进时限超标"),
    "format_missing": ("format", "缺少规定开场语"),
    "service_dismissive": ("service", "服务回复明显敷衍"),
    "operation_model": ("operation", "沟通已确认型号但工单漏填"),
}
SEMANTIC_RULES = {"fatal_review", "business_incomplete", "service_dismissive"}


def messages_for(data, subject):
    return [message for message in data["messages"] if message["role"] == "human" and message["author"] == subject]


def service_minutes(start, end, calendar):
    start, end = start.astimezone(BEIJING), end.astimezone(BEIJING)
    if calendar is None or end <= start:
        return max(0, (end - start).total_seconds() / 60)
    day, total = start.date(), 0.0
    while day <= end.date():
        if day.weekday() in calendar.weekdays and day not in calendar.closed_dates:
            opened = datetime.combine(day, calendar.opens, BEIJING)
            closed = datetime.combine(day, calendar.closes, BEIJING)
            total += max(0, (min(end, closed) - max(start, opened)).total_seconds() / 60)
        day += timedelta(days=1)
    return total


def preliminary(data, subject, config):
    notes = []
    replies = messages_for(data, subject)
    customers = [message for message in data["messages"] if message["role"] == "customer"]
    missing = [*data["missing"]]
    if not replies or not customers:
        missing.append("缺少可核对的客户消息或实际回复")
    if replies and config["require_greeting"] and not replies[0]["text"].startswith(("你好", "您好")):
        notes.append({"rule_id": "format_missing", "evidence": [replies[0]["id"]]})
    model = next((message for message in customers if re.search(r"型号\s*(?:是|为|[:：])\s*[a-zA-Z][\w-]+",
                                                                message["text"])), None)
    if model and not data["facts"].get("product_ref") and data["assignee"] == subject:
        notes.append({"rule_id": "operation_model", "evidence": [model["id"], "fact:product_ref"]})
    calendar = ServiceCalendar.model_validate(data["calendar"]) if data["calendar"] else None
    pending = None
    for message in data["messages"]:
        if message["role"] == "customer":
            pending = pending or message
        elif message["role"] == "human" and pending:
            if message["author"] == subject and service_minutes(datetime.fromisoformat(pending["at"]),
                    datetime.fromisoformat(message["at"]), calendar) > config["follow_up_minutes"]:
                notes.append({"rule_id": "process_late", "evidence": [pending["id"], message["id"]]})
            pending = None
    risk = any(re.search(r"投诉|反复|差评|没人回复", message["text"]) for message in customers + replies)
    return notes, missing, risk


def mock_judge(data, subject):
    """模拟输出契约，用固定中文样例验证流程、证据及计分。"""
    replies = messages_for(data, subject)
    findings = []
    for reply in replies:
        if re.search(r"(?:删|撤).{0,5}差评", reply["text"]):
            findings.append({"rule_id": "fatal_review", "evidence": [reply["id"]]})
        if re.search(r"别再问|自己想办法|懒得处理", reply["text"]):
            findings.append({"rule_id": "service_dismissive", "evidence": [reply["id"]]})
    if replies:
        dialogue = " ".join(reply["text"] for reply in replies)
        for message in data["messages"]:
            text = message["text"]
            if message["role"] != "customer" or not re.search(r"另外|同时|还想问", text):
                continue
            missing_topic = any(topic in text and topic not in dialogue for topic in ("保修", "退款", "换货"))
            if missing_topic:
                findings.append({"rule_id": "business_incomplete", "evidence": [message["id"], replies[-1]["id"]]})
                break
    distinct = {item["rule_id"]: item for item in findings}
    return {"findings": list(distinct.values())}


def checked_findings(raw, data, subject, *, semantic_only=False):
    judgment = QualityJudgment.model_validate(raw)
    message_map = {message["id"]: message for message in data["messages"]}
    checked = []
    for row in judgment.findings:
        rule = row.rule_id
        if semantic_only and rule not in SEMANTIC_RULES:
            raise ValueError("模型只能提交语义规则")
        evidence = [message_map[ref] for ref in row.evidence if ref != "fact:product_ref"]
        roles = {message["role"] for message in evidence}
        if any(message["role"] == "human" and message["author"] != subject for message in evidence):
            raise ValueError("包含其他客服的回复引用")
        if "fact:product_ref" in row.evidence and rule != "operation_model":
            raise ValueError("规则引用了不适用的工单字段")
        if rule in {"business_incomplete", "process_late"} and "customer" not in roles:
            raise ValueError("缺少客户消息")
        if rule == "operation_model":
            if "customer" not in roles or "fact:product_ref" not in row.evidence or data["facts"].get("product_ref") or data["assignee"] != subject:
                raise ValueError("不符合漏填型号规则的归责条件")
        elif not any(message["role"] == "human" and message["author"] == subject for message in evidence):
            raise ValueError("缺少受评客服的正式回复")
        checked.append(row.model_dump())
    return checked


def score(findings, config, *, confirmed=False, missing=()):
    distinct = {item["rule_id"]: item for item in findings}
    amounts = defaultdict(int)
    items = []
    for rule, item in distinct.items():
        category, label = RULES[rule]
        deduction = config["deductions"].get(rule, 0)
        amounts[category] += deduction
        items.append({**item, "label": label, "category": category, "deduction": deduction})
    total = sum(min(amounts[key], limit) for key, limit in config["caps"].items())
    fatal = "fatal_review" in distinct
    value = 0 if confirmed and fatal else None if (fatal or missing) else max(0, 100 - total)
    return {"findings": items, "score": value, "fatal": fatal, "missing": list(missing)}
