from uuid import UUID, uuid4

import pytest

from app.domain.enums import Role
from app.services.experiences import process_candidate
from test_p02 import create
from test_p11 import login


pytestmark = pytest.mark.integration


def candidate(client, **scope):
    scope = {"product_ref": "P13-DEMO", "firmware_version": "1.0", **scope}
    ticket = create(client, feedback_text="模拟连接反复断开", **scope)
    response = client.post(f"/api/v1/tickets/{ticket['ticket_id']}/close", json={
        "action_id": str(uuid4()), "expected_version": ticket["version"], "outcome": "resolved",
        "reason": "复核连接已经恢复", "verified_steps": "重新配对后复测连接稳定",
    })
    assert response.status_code == 200
    assert process_candidate(UUID(ticket["ticket_id"]))
    row, = client.get("/api/v1/experiences", params={"ticket_id": ticket["ticket_id"]}).json()["items"]
    return row


def review(client, row, decision="review"):
    result = client.post(f"/api/v1/experiences/{row['id']}/review", json={
        "decision": decision, "reason": "检查确认记录", "action_id": str(uuid4()), "expected_version": row["version"]})
    assert result.status_code == 200
    return result.json()


def path(row):
    return f"/api/v1/experiences/{row['id']}/publications"


def command():
    return {"action_id": str(uuid4()), "reason": "复核范围与操作"}


def find(client, **scope):
    response = client.post("/api/v1/experience-recall", json={
        "query": "连接断开", "product_ref": "P13-DEMO", "firmware_version": "1.0", **scope})
    assert response.status_code == 200
    return response.json()


def test_publication_access_scope_version_withdrawal_and_archive(api, account_factory):
    client, business, password = api
    admin, admin_secret = account_factory(Role.KNOWLEDGE_ADMIN)
    raw = candidate(client, platform="android", region="CN")
    assert not find(client, platform="android", region="CN")
    assert client.post(path(raw), json=command()).status_code == 403
    login(client, admin, admin_secret)
    denied = client.post(path(raw), json=command())
    assert denied.status_code == 409 and denied.json()["error"]["code"] == "EXPERIENCE_REVIEW_REQUIRED"
    login(client, business, password)
    verified = review(client, raw)
    login(client, admin, admin_secret)
    assert any(row["id"] == verified["id"] for row in client.get("/api/v1/experience-release-candidates").json())
    payload = command()
    response = client.post(path(verified), json=payload)
    assert response.status_code == 201, response.text
    release = response.json()
    assert release["revision"] == 1 and client.post(path(verified), json=payload).json() == release
    login(client, business, password)
    assert not find(client, platform="android")
    assert not find(client, platform="ios", region="CN")
    assert not find(client, platform="android", region="CN", firmware_version="2.0")
    found, = find(client, platform="android", region="CN")
    assert found["verified_steps"] == "重新配对后复测连接稳定" and "evidence_refs" not in found
    assert found["source_ticket_id"] == raw["source_ticket_id"]
    login(client, admin, admin_secret)
    withdrawn = client.post(path(verified) + "/1/withdraw", json=command()).json()
    assert withdrawn["status"] == "withdrawn"
    login(client, business, password)
    assert not find(client, platform="android", region="CN")
    login(client, admin, admin_secret)
    new = client.post(path(verified), json=command()).json()
    assert new["revision"] == 2
    assert client.post(path(verified) + "/1/withdraw", json=command()).status_code == 409
    login(client, business, password)
    assert review(client, verified, "archive")["status"] == "archived"
    assert not find(client, platform="android", region="CN")
    login(client, admin, admin_secret)
    assert [row["status"] for row in client.get(path(verified)).json()] == ["withdrawn", "withdrawn"]


def test_experience_rejects_overlapping_scope_allows_disjoint_scope(api, account_factory):
    client, _, _ = api
    # 独立型号避免不同测试在复用的本地验收库里共享逻辑槽位。
    model = "P13-" + uuid4().hex
    rows = [review(client, candidate(client, **scope)) for scope in (
        {"product_ref": model, "platform": "android"},
        {"product_ref": model, "platform": "android", "region": "CN"},
        {"product_ref": model, "platform": "ios"},
    )]
    admin, secret = account_factory(Role.KNOWLEDGE_ADMIN)
    login(client, admin, secret)
    results = [client.post(path(row), json=command()) for row in rows]
    assert [row.status_code for row in results] == [201, 409, 201]
    assert results[1].json()["error"]["code"] == "EXPERIENCE_OVERLAP"
