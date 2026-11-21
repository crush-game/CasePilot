import asyncio
import json
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.enums import Role
from app.knowledge.hybrid import build_index
from app.knowledge.schemas import DocumentMetadata
from app.manage import create_user
from app.repositories.models import LogArtifact
from app.services.knowledge import create_document
from app.workers.ingestion import run_once as ingest
from test_p06 import isolated
from test_p07 import advance, response as knowledge_response
from test_p08 import fault_agent, response as fault_response


@pytest.mark.integration
@pytest.mark.parametrize("kind,expected", [("consultation", {"kb"}), ("wifi", {"logev"}), ("mixed", {"kb", "logev"})])
def test_phase_one_routes_work_through_one_persisted_run(fault_agent, kind, expected):
    engine, provider, create, inspect, _, _ = fault_agent
    with Session(engine, expire_on_commit=False) as db:
        admin = create_user(db, "p10_" + uuid4().hex, "fixture-password", Role.KNOWLEDGE_ADMIN)
        doc = create_document(db, admin, str(uuid4()), DocumentMetadata(
            doc_key="p10-connection", version=1, title="连接检查", product_scope=["PILOT-01"],
            firmware_versions=["1.0"], regions=["*"], channels=["*"]),
            "sample.md", "连接中断时请检查连接设置，再根据日志核查。".encode())
    assert ingest(UUID(doc["job_id"]))

    def respond(request):
        if not request.url.path.endswith("/chat/completions"):
            return knowledge_response(request)
        body = json.loads(request.content)
        system, observation = (json.loads(item["content"]) for item in body["messages"])
        schema = system["output_schema"]["title"]
        if schema == "ParsedRequest" and kind == "consultation":
            return knowledge_response(request)
        if schema != "InvestigationDecision":
            return fault_response(request, "wifi")
        if kind == "wifi":
            action = "generate_solution" if observation.get("fault_report") else "fault_investigation"
        elif not observation.get("last_subtask"):
            action = "knowledge_investigation"
        elif kind == "mixed" and not observation.get("fault_report"):
            action = "fault_investigation"
        else:
            action = "generate_solution"
        decision = {"action": action, "fault_domains": ["wifi"], "reason": "按已取得的证据安排下一步",
                    "query": "连接设置", "goal": "核对连接", "data_source": "mock", "evidence_refs": []}
        return httpx.Response(200, json={"model": body["model"], "choices": [
            {"finish_reason": "stop", "message": {"content": json.dumps(decision)}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 100}})

    client = provider()
    client.transport = httpx.MockTransport(respond)
    if "kb" in expected:
        asyncio.run(build_index(client))
    value, _ = create(feedback_text={"consultation": "怎样设置连接？", "wifi": "行驶中连接断开",
                                    "mixed": "熄火断连，结合指南和日志排查"}[kind])
    assert advance(UUID(value["run_id"]), client)
    status, reason, state, _ = inspect(value)
    assert status == "PENDING_CONFIRMATION", reason
    solution = state["solution"]
    assert {ref.split(":")[0] for ref in solution["evidence_refs"]} == expected
    assert solution["draft_validation"] == "passed" and not solution["reviewed"]
    with Session(engine) as db:
        assert (db.scalar(select(LogArtifact)) is not None) == ("logev" in expected)
