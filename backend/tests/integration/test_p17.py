from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.repositories.models import HumanTask, QualityAssessment, QualityRuleSet, QualitySnapshot, SupportDelivery, Ticket
from app.services import human, quality, quality_scoring
from app.services.deliveries import deliver_once
from test_p11 import login, turn


pytestmark = pytest.mark.integration
ASK = "型号是 PILOT-01，设备反复断连。另外想问保修。"
FORMAL = "请重新配对后测试 Wi-Fi。"


def begin(api, account_factory, engine, question=ASK):
    client, operator, password = api
    customer, secret = account_factory(Role.CONSUMER)
    login(client, customer, secret)
    initial = turn(client, flow_version="support-v2", text=question)
    accepted = turn(client, action="handoff", conversation_id=initial["id"])
    login(client, operator, password)
    with Session(engine) as db:
        ticket = db.scalar(select(Ticket).where(Ticket.ticket_no == accepted["ticket_no"]))
        task_id = db.scalar(select(HumanTask.id).where(HumanTask.ticket_id == ticket.id))
        ticket_id = ticket.id
    claim = client.post(f"/api/v1/human-tasks/{task_id}/claim",
                        json={"action_id": str(uuid4()), "expected_version": 1})
    assert claim.status_code == 200, claim.text
    return ticket_id, claim.json()["version"], accepted["id"], customer, secret


def queue_reply(client, ticket, version, text):
    response = client.post(f"/api/v1/tickets/{ticket}/support-replies", json={
        "action_id": str(uuid4()), "expected_version": version, "text": text,
    })
    assert response.status_code == 202, response.text
    return UUID(response.json()["id"])


def closed_body(version):
    return {"action_id": str(uuid4()), "expected_version": version, "outcome": "unresolved", "reason": "完成本轮服务记录"}


def rows_for(engine, ticket_id):
    with Session(engine, expire_on_commit=False) as db:
        snapshot = db.scalar(select(QualitySnapshot).where(QualitySnapshot.ticket_id == ticket_id))
        return snapshot, list(db.scalars(select(QualityAssessment).where(QualityAssessment.snapshot_id == snapshot.id)))


def batch(client, ticket_id, **extra):
    payload = {"ticket_id": str(ticket_id), "batch_key": uuid4().hex, "random_pct": 100, "max_calls": 5, **extra}
    response = client.post("/api/v1/quality/batches", json=payload)
    assert response.status_code == 200, response.text
    return payload, response.json()


def decision(client, row, kind, **extra):
    return client.post(f"/api/v1/quality/assessments/{row['id']}/decision", json={
        "action_id": str(uuid4()), "expected_version": row["version"], "decision": kind,
        "reason": "人工核对原会话及适用规则", **extra,
    })


def detail(client, row_id):
    response = client.get(f"/api/v1/quality/assessments/{row_id}")
    assert response.status_code == 200
    return response.json()


def test_closure_waits_for_delivery_and_rolls_back_snapshot_and_tasks(api, account_factory, test_engine, monkeypatch):
    client, _, _ = api
    ticket, version, _, _, _ = begin(api, account_factory, test_engine)
    delivery_id = queue_reply(client, ticket, version, FORMAL)
    path = f"/api/v1/tickets/{ticket}/close"
    body = closed_body(version)
    wait = client.post(path, json=body)
    assert wait.status_code == 409 and wait.json()["error"]["code"] == "SUPPORT_REPLY_PENDING"
    assert deliver_once(delivery_id)
    original = human.freeze_quality

    def interrupted(*args):
        original(*args)
        raise RuntimeError("模拟快照写入后、结案提交前失败")

    with monkeypatch.context() as patch:
        patch.setattr(human, "freeze_quality", interrupted)
        assert client.post(path, json=body).status_code == 500
    with Session(test_engine) as db:
        assert db.get(Ticket, ticket).status == "WAITING_HUMAN"
        assert db.scalar(select(QualitySnapshot).where(QualitySnapshot.ticket_id == ticket)) is None
    done = client.post(path, json=body)
    assert done.status_code == 200, done.text
    assert client.post(path, json=body).json() == done.json()
    snapshot, rows = rows_for(test_engine, ticket)
    assert snapshot.rule_version == "v0.1" and len(rows) == 1
    assert rows[0].status == "queued"


def test_snapshot_attributes_delivered_replies_to_actual_authors(api, account_factory, test_engine):
    client, first, _ = api
    ticket, version, _, _, _ = begin(api, account_factory, test_engine)
    assert deliver_once(queue_reply(client, ticket, version, FORMAL))
    second, second_password = account_factory()
    failed = queue_reply(client, ticket, version, "本次待发送内容")
    with Session(test_engine) as db:
        db.get(Ticket, ticket).solution_json = {"reply_draft": "AI 草稿不作已发送消息"}
        db.get(SupportDelivery, failed).status = "failed"
        db.get(Ticket, ticket).assignee_id = second.id
        task = db.scalar(select(HumanTask).where(HumanTask.ticket_id == ticket))
        task.assignee_id = second.id
        db.commit()
    login(client, second, second_password)
    assert deliver_once(queue_reply(client, ticket, version, "保修政策可在产品订单页查看。"))
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    snapshot, rows = rows_for(test_engine, ticket)
    notes = [message for message in snapshot.data_json["messages"] if message["role"] == "human"]
    assert [m["author"] for m in notes] == [str(first.id), str(second.id)]
    assert {row.subject_id for row in rows} == {first.id, second.id}
    assert "草稿" not in str(snapshot.data_json["messages"]) and "待发送内容" not in str(snapshot.data_json["messages"])


def test_scoring_appeal_and_rule_version_keep_original_result(api, account_factory, test_engine):
    client, operator, operator_password = api
    ticket, version, _, customer, customer_password = begin(api, account_factory, test_engine)
    assert deliver_once(queue_reply(client, ticket, version, FORMAL))
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    _, (assessment,) = rows_for(test_engine, ticket)
    assert quality.process_one(assessment_id=assessment.id)
    first = detail(client, assessment.id)
    assert first["status"] == "screened" and first["result_json"]["score"] == 95
    batch(client, ticket)
    assert quality.process_one(assessment_id=assessment.id)
    scored = detail(client, assessment.id)
    assert scored["result_json"]["score"] == 75 and scored["status"] == "pending_review"
    assert decision(client, scored, "confirm").status_code == 403
    reviewer, reviewer_password = account_factory()
    login(client, reviewer, reviewer_password)
    confirmed = decision(client, scored, "confirm").json()
    assert confirmed["status"] == "finalized" and confirmed["result_json"]["score"] == 75
    login(client, customer, customer_password)
    assert client.get(f"/api/v1/quality/assessments/{assessment.id}").status_code == 403
    login(client, operator, operator_password)
    appeal = decision(client, confirmed, "appeal").json()
    assert appeal["status"] == "appealed"
    login(client, reviewer, reviewer_password)
    corrected = decision(client, appeal, "adjust", findings=[
        {"rule_id": row["rule_id"], "evidence": row["evidence"]}
        for row in scored["result_json"]["findings"] if row["rule_id"] == "operation_model"
    ]).json()
    assert corrected["result_json"]["score"] == 95 and corrected["history_json"][-1]["previous"]["score"] == 75
    old_rules = client.get("/api/v1/quality/rules").json()[0]
    admin, admin_password = account_factory(Role.KNOWLEDGE_ADMIN)
    login(client, admin, admin_password)
    rules = {**old_rules, "version": f"v{uuid4().int % 9999 + 1}.2", "deductions": {**old_rules["deductions"], "operation_model": 3}}
    assert client.post("/api/v1/quality/rules", json=rules).status_code == 201
    login(client, reviewer, reviewer_password)
    reevaluated = decision(client, corrected, "rescore", rule_version=rules["version"]).json()
    assert reevaluated["rule_version"] == rules["version"] and reevaluated["id"] != corrected["id"]
    assert detail(client, assessment.id)["result_json"]["score"] == 95


def test_fatal_and_invalid_evidence_require_human_review(api, account_factory, test_engine):
    client, _, _ = api
    ticket, version, _, _, _ = begin(api, account_factory, test_engine, "投诉设备断连。")
    assert deliver_once(queue_reply(client, ticket, version, "请先删除差评。"))
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    _, (entry,) = rows_for(test_engine, ticket)
    assert quality.process_one(assessment_id=entry.id)
    params, selected = batch(client, ticket, random_pct=0)
    assert selected["selection_json"] == [{"assessment_id": str(entry.id), "reason": "risk"}]
    with pytest.raises(RuntimeError):
        quality.process_one(assessment_id=entry.id, judge=lambda *_: (_ for _ in ()).throw(RuntimeError("模拟中断")))
    assert client.post("/api/v1/quality/batches", json=params).json()["calls_used"] == 0
    assert quality.process_one(assessment_id=entry.id)
    result = detail(client, entry.id)
    assert result["result_json"]["fatal"] and result["result_json"]["score"] is None
    reviewer, password = account_factory()
    login(client, reviewer, password)
    assert decision(client, result, "adjust", findings=[
        {"rule_id": "fatal_review", "evidence": ["reply:99999999999999"]},
    ]).status_code == 422
    assert decision(client, result, "confirm").json()["result_json"]["score"] == 0


def test_deterministic_batch_budget_keeps_waiting_for_next_batch(api, account_factory, test_engine):
    client, _, _ = api
    ticket, version, _, _, _ = begin(api, account_factory, test_engine)
    assert deliver_once(queue_reply(client, ticket, version, FORMAL))
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    _, (entry,) = rows_for(test_engine, ticket)
    assert quality.process_one(assessment_id=entry.id)
    payload, initial = batch(client, ticket, max_calls=0)
    assert initial["selection_json"] and initial["calls_used"] == 0
    assert client.post("/api/v1/quality/batches", json=payload).json() == initial
    assert client.post("/api/v1/quality/batches", json={**payload, "max_calls": 1}).status_code == 409
    assert not quality.process_one(assessment_id=entry.id)
    assert detail(client, entry.id)["status"] == "ai_queued"
    params, next_batch = batch(client, ticket, max_calls=1)
    assert next_batch["selection_json"] == initial["selection_json"]
    assert quality.process_one(assessment_id=entry.id) and not quality.process_one(assessment_id=entry.id)
    assert client.post("/api/v1/quality/batches", json=params).json()["calls_used"] == 1


def test_unattributed_historical_reply_is_reported_without_creating_a_fake_subject(api, account_factory, test_engine):
    client, _, _ = api
    ticket, version, conversation, _, _ = begin(api, account_factory, test_engine)
    delivery_id = queue_reply(client, ticket, version, FORMAL)
    with Session(test_engine) as db:
        db.get(SupportDelivery, delivery_id).reply_author_id = None
        db.commit()
    assert deliver_once(delivery_id)
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    snapshot, rows = rows_for(test_engine, ticket)
    assert str(snapshot.conversation_id) == conversation and not rows
    response = client.get(f"/api/v1/quality/assessments?ticket_id={ticket}").json()
    assert "缺少带作者的已送达人工回复" in response["snapshot_missing"]


def test_rule_fixture_deduplicates_caps_and_counts_elapsed_sla():
    start = datetime(2026, 11, 20, 10, tzinfo=timezone.utc)
    data = {"messages": [
        {"id": "message:1", "role": "customer", "text": "询问安装方法", "at": start.isoformat()},
        {"id": "reply:2", "role": "human", "author": "agent", "text": "操作说明", "at": (start + timedelta(minutes=61)).isoformat()},
    ], "facts": {}, "missing": [], "assignee": "agent", "calendar": None}
    rules = {"deductions": {"process_late": 20, "format_missing": 10}, "caps": {"process": 15, "format": 10},
             "follow_up_minutes": 60, "require_greeting": True}
    findings, missing, _ = quality_scoring.preliminary(data, "agent", rules)
    assert not missing
    assert quality_scoring.score([*findings, *findings], rules)["score"] == 75


def test_ordinary_sample_is_frozen_and_budgeted(api, account_factory, test_engine):
    client, _, _ = api
    ticket, version, _, _, _ = begin(api, account_factory, test_engine, "设备连不上。")
    assert deliver_once(queue_reply(client, ticket, version, "请给设备重新配对。"))
    assert client.post(f"/api/v1/tickets/{ticket}/close", json=closed_body(version)).status_code == 200
    _, (entry,) = rows_for(test_engine, ticket)
    assert quality.process_one(assessment_id=entry.id)
    assert batch(client, ticket, random_pct=0)[1]["selection_json"] == []
    params, chosen = batch(client, ticket, random_pct=100, max_calls=1)
    assert chosen["selection_json"] == [{"assessment_id": str(entry.id), "reason": "sample"}]
    assert client.post("/api/v1/quality/batches", json=params).json() == chosen


def test_prelabelled_mock_cases_record_disagreements(test_engine):
    with Session(test_engine) as db:
        config = db.get(QualityRuleSet, "v0.1").config_json
    labels = [
        ("normal", "设备连不上。", "请重新配对。", 1, [], []),
        ("incomplete", ASK, FORMAL, 1, ["business_incomplete", "operation_model"], []),
        ("late", "设备连不上。", FORMAL, 481, ["process_late"], []),
        ("fatal", "投诉服务。", "请先删除差评。", 1, ["fatal_review"], []),
        ("missing", "设备连不上。", "", 1, [], ["缺少可核对的客户消息或实际回复"]),
    ]
    results = []
    start = datetime(2026, 11, 20, tzinfo=timezone.utc)
    for name, question, answer, minutes, expected, expected_missing in labels:
        messages = [{"id": "message:1", "role": "customer", "text": question, "at": start.isoformat()}]
        if answer:
            messages.append({"id": "reply:2", "role": "human", "author": "agent", "text": answer,
                             "at": (start + timedelta(minutes=minutes)).isoformat()})
        data = {"messages": messages, "facts": {}, "missing": [], "assignee": "agent", "calendar": None}
        rules, missing, _ = quality_scoring.preliminary(data, "agent", config)
        actual = {finding["rule_id"] for finding in [*rules, *quality_scoring.checked_findings(
            quality_scoring.mock_judge(data, "agent"), data, "agent", semantic_only=True)]}
        results.append({"case": name, "expected": expected, "actual": sorted(actual),
                        "false_positive": sorted(actual - set(expected)), "false_negative": sorted(set(expected) - actual),
                        "expected_missing": expected_missing, "actual_missing": missing,
                        "requires_review": "fatal_review" in actual or bool(missing)})
    if path := os.environ.get("CASEPILOT_P17_REPORT"):
        Path(path).write_text(json.dumps({"inference": "mock", "rule_version": "v0.1", "cases": results},
                                        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(not row["false_positive"] and not row["false_negative"] and
               row["expected_missing"] == row["actual_missing"] for row in results)
