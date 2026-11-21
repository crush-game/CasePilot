from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import FeedbackInput, ReviewInput
from app.domain.errors import AppError
from app.repositories.models import AuditEvent, Experience, HumanTask, KBChunk, KBDocument, LogArtifact, Ticket
from app.services.experiences import process_candidate
from app.services.human import contacted, review
from test_p02 import create as create_ticket, detail
from test_p06 import isolated
from test_p07 import advance, agent, prepare
from test_p08 import fault_agent


pytestmark = pytest.mark.integration


def create_case(client, **fields):
    return create_ticket(client, occurred_at="2026-11-21T10:00:00+08:00", **fields)


def post_action(client, path, version, **fields):
    return client.post("/api/v1" + path, json={"expected_version": version, "action_id": str(uuid4()), **fields})


def test_explicit_resolution_enqueues_once_and_review_is_audited(api, test_engine):
    client, _, _ = api
    created = create_case(client, device_ref="P09-DEVICE", feedback_text="连接不稳定，联系 p09-private@example.test")
    ticket_id = UUID(created["ticket_id"])
    advance(UUID(created["run_id"]), None)
    path = f"/tickets/{ticket_id}"
    ticket = detail(client, ticket_id)
    solution = ticket["solution_json"]
    assert solution["draft_validation"] == "passed" and solution["evidence_refs"]
    assert solution["confirmed_facts"]["occurred_at"] == ticket["occurred_at_original"]
    assert solution["observations"] == []
    assert not client.get("/api/v1/experiences", params={"ticket_id": str(ticket_id)}).json()["items"]
    approved = post_action(client, path + "/review", ticket["version"], decision="approve").json()
    pending = post_action(client, path + "/customer-feedback", approved["version"],
                          outcome="contacted", reason="已联系").json()
    assert not process_candidate(ticket_id)
    action = str(uuid4())
    close_body = {"action_id": action, "expected_version": pending["version"], "outcome": "resolved",
                  "reason": "已核验连接恢复 token=PRIVATE_P09", "verified_steps": "重新连接后验证可用"}
    closed = client.post("/api/v1" + path + "/close", json=close_body)
    assert closed.status_code == 200 and closed.json()["status"] == "RESOLVED"
    assert client.post("/api/v1" + path + "/close", json=close_body).json() == closed.json()
    assert not client.get("/api/v1/experiences", params={"ticket_id": str(ticket_id)}).json()["items"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(process_candidate, [ticket_id, ticket_id])) == [False, True]
    result = client.get("/api/v1/experiences", params={"ticket_id": str(ticket_id)}).json()
    item, = result["items"]
    assert item["source_run_id"] == created["run_id"] and item["source_action_id"] == action
    assert item["result_version"] == closed.json()["version"] and item["status"] == "candidate"
    assert item["content_json"]["verified_steps"] == "重新连接后验证可用"
    assert item["content_json"]["evidence_refs"] == solution["evidence_refs"]
    assert "PRIVATE_P09" not in str(item) and "p09-private@example.test" not in str(item)
    experience_path = "/api/v1/experiences/" + item["id"] + "/review"
    review_body = {"action_id": str(uuid4()), "expected_version": item["version"], "decision": "review", "reason": "已复核来源"}
    reviewed = client.post(experience_path, json=review_body)
    assert reviewed.status_code == 200 and reviewed.json()["status"] == "reviewed"
    assert client.post(experience_path, json=review_body).json() == reviewed.json()
    assert client.post(experience_path, json={**review_body, "action_id": str(uuid4())}).status_code == 409
    archived = post_action(client, experience_path.removeprefix("/api/v1"), reviewed.json()["version"],
                           decision="archive", reason="撤出待进一步验证的样例")
    assert archived.status_code == 200 and archived.json()["status"] == "archived"
    with Session(test_engine) as db:
        records = list(db.scalars(select(AuditEvent).where(AuditEvent.ticket_id == ticket_id,
            AuditEvent.operation == "experiences.review").order_by(AuditEvent.expected_version)))
        assert [row.result["status"] for row in records] == ["reviewed", "archived"]


def test_unresolved_close_and_contacted_never_create_candidate(api, test_engine):
    client, _, _ = api
    created = create_case(client, device_ref="P09-OPEN")
    ticket_id = UUID(created["ticket_id"])
    advance(UUID(created["run_id"]), None)
    ticket = detail(client, ticket_id)
    result = post_action(client, f"/tickets/{ticket_id}/close", ticket["version"],
                         outcome="unresolved", reason="没有确认解决")
    assert result.status_code == 200 and result.json()["status"] == "CLOSED_UNRESOLVED"
    assert not process_candidate(ticket_id)
    with Session(test_engine) as db:
        assert db.scalar(select(Experience).where(Experience.source_ticket_id == ticket_id)) is None


def test_customer_confirmation_is_recorded_without_inventing_effective_steps(api):
    client, _, _ = api
    created = create_case(client, device_ref="P09-CUSTOMER")
    ticket_id = UUID(created["ticket_id"])
    advance(UUID(created["run_id"]), None)
    ticket = detail(client, ticket_id)
    result = post_action(client, f"/tickets/{ticket_id}/customer-feedback", ticket["version"],
                         outcome="resolved", reason="客户明确回复已解决")
    assert result.status_code == 200 and process_candidate(ticket_id)
    item, = client.get("/api/v1/experiences", params={"ticket_id": str(ticket_id)}).json()["items"]
    content = item["content_json"]
    assert content["confirmation"] == "customer_confirmed" and not content["verified_steps"]
    assert "未记录经核验的有效措施。" in content["limitations"]


def test_experiences_requires_business_role(api, account_factory):
    from app.domain.enums import Role
    client, _, _ = api
    admin, password = account_factory(Role.KNOWLEDGE_ADMIN)
    assert client.post("/api/v1/auth/login", json={"login": admin.login, "password": password}).status_code == 200
    assert client.get("/api/v1/experiences").status_code == 403


def test_projection_rechecks_citations_even_after_graph_validation(agent, monkeypatch):
    from app.workers import runtime
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    created, _ = create()
    project = runtime.project_result

    def archive_at_projection(ctx, snapshot, failure_reason=None):
        assert snapshot.values["complete"]
        with Session(engine) as db:
            ref = snapshot.values["solution"]["evidence_refs"][0]
            doc = db.get(KBDocument, db.get(KBChunk, UUID(ref[3:])).document_id)
            doc.status = "archived"
            db.commit()
        return project(ctx, snapshot, failure_reason)

    monkeypatch.setattr(runtime, "project_result", archive_at_projection)
    advance(UUID(created["run_id"]), provider)
    assert inspect(created)[:2] == ("WAITING_HUMAN", "EVIDENCE_NOT_APPLICABLE")
    with Session(engine) as db:
        assert not db.get(Ticket, UUID(created["ticket_id"])).solution_json
        task = db.scalar(select(HumanTask))
        assert task.reason_code == "EVIDENCE_NOT_APPLICABLE" and task.payload_json["requires_reinvestigation"]


def test_facts_and_observations_stay_separate_and_stale_log_blocks_approval(fault_agent):
    engine, provider, create, inspect, _, _ = fault_agent
    value, actor = create()
    advance(UUID(value["run_id"]), provider())
    ticket_id = UUID(value["ticket_id"])
    with Session(engine) as db:
        ticket = db.get(Ticket, ticket_id)
        draft = ticket.solution_json
        assert draft["confirmed_facts"]["platform"] == "android"
        assert "未确认" not in draft["confirmed_facts"]
        assert draft["observations"] and all(set(row["evidence_refs"]) <= set(draft["evidence_refs"])
                                              for row in draft["observations"])
        version = ticket.version
        artifact = db.scalar(select(LogArtifact))
        artifact.original_bytes = b"corrupted"
        db.commit()
        with pytest.raises(AppError) as caught:
            review(db, actor, ticket_id, ReviewInput(action_id=uuid4(), expected_version=version, decision="approve"))
        assert caught.value.code == "EVIDENCE_NOT_APPLICABLE"
        db.rollback()
        assert not db.get(Ticket, ticket_id).solution_json["reviewed"]


def test_archived_after_approval_blocks_contact_record(agent):
    engine, session, create, inspect = agent
    provider = session()
    prepare(engine, provider)
    value, actor = create()
    advance(UUID(value["run_id"]), provider)
    ticket_id = UUID(value["ticket_id"])
    with Session(engine) as db:
        ticket = db.get(Ticket, ticket_id)
        reviewed = review(db, actor, ticket.id, ReviewInput(action_id=uuid4(), expected_version=ticket.version, decision="approve"))
        ref = db.get(Ticket, ticket_id).solution_json["evidence_refs"][0]
        db.get(KBDocument, db.get(KBChunk, UUID(ref[3:])).document_id).status = "archived"
        db.commit()
        with pytest.raises(AppError) as caught:
            contacted(db, actor, ticket_id, FeedbackInput(action_id=uuid4(), expected_version=reviewed["version"],
                                                           reason="准备联系", outcome="contacted"))
        assert caught.value.code == "EVIDENCE_NOT_APPLICABLE"
        db.rollback()
        assert db.get(Ticket, ticket_id).status == "PENDING_CONFIRMATION"
