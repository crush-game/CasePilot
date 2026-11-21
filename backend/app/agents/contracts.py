"""P07 只输出可检查的决定、证据与缺口，不接受模型自定义工具或权限。"""

from typing import Literal

from pydantic import Field

from app.tools.contracts import Contract


class AgentPolicy(Contract):
    version: Literal["p07-v1", "p08-v1"] = "p07-v1"
    max_model_calls: int = Field(default=20, ge=1, le=20)
    max_tokens: int = Field(default=100000, ge=1, le=500000)
    max_cost: float = Field(default=0.5, gt=0, le=5, allow_inf_nan=False)
    max_tools: int = Field(default=12, ge=1, le=12)
    max_knowledge_tasks: int = Field(default=2, ge=1, le=2)
    max_run_calls: int = Field(default=100, ge=1, le=100)
    max_run_tokens: int = Field(default=500000, ge=1, le=1000000)
    max_run_cost: float = Field(default=2.5, gt=0, le=5, allow_inf_nan=False)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_steps: int = Field(default=64, ge=8, le=150)
    max_fault_tasks: int = Field(default=2, ge=1, le=2)


class ParsedRequest(Contract):
    request_type: Literal["consultation", "fault", "unsupported", "unknown"]
    question: str = Field(min_length=1, max_length=500)
    symptoms: list[str] = Field(max_length=10)
    unresolved_items: list[str] = Field(max_length=10)
    data_source: Literal["mock"]
    evidence_refs: list[str] = Field(max_length=0)


class SupervisorDecision(Contract):
    action: Literal["knowledge_investigation", "generate_solution", "fault_investigation", "human_interrupt"]
    reason: str = Field(min_length=1, max_length=500)
    goal: str = Field(default="", max_length=500)
    query: str = Field(default="", max_length=500)
    unresolved_items: list[str] = Field(default_factory=list, max_length=10)
    data_source: Literal["mock"]
    evidence_refs: list[str] = Field(max_length=12)


class Finding(Contract):
    point: str = Field(min_length=1, max_length=600)
    applicability: str = Field(min_length=1, max_length=300)
    evidence_refs: list[str] = Field(min_length=1, max_length=6)


class KnowledgeAssessment(Contract):
    status: Literal["sufficient", "partial", "no_evidence", "conflicting"]
    findings: list[Finding] = Field(max_length=6)
    unresolved_items: list[str] = Field(max_length=10)
    conflicts: list[list[str]] = Field(max_length=6)
    suggested_action: Literal["finish", "rewrite", "context", "human"]
    rewrite_query: str = Field(default="", max_length=500)
    context_refs: list[str] = Field(default_factory=list, max_length=2)
    data_source: Literal["mock"]
    evidence_refs: list[str] = Field(max_length=12)


class SubtaskResult(Contract):
    status: Literal["completed", "partial", "needs_human", "error"]
    evidence_refs: list[str]
    findings: list[Finding]
    unresolved_items: list[str]
    stop_reason: str
    conflicts: list[list[str]] = Field(default_factory=list)
    source_actions: list[str] = Field(default_factory=list)
    data_source: Literal["mock"] = "mock"


SCOPE_FIELDS = ("product_ref", "firmware_version", "region", "channel")


def configuration_snapshot():
    from app.config import get_settings
    from app.providers.configuration import load_provider_config
    settings = get_settings()
    if settings.workflow_graph_version == "mock-v1":
        return {"solution_contract": "p09-v1"}
    value = {"solution_contract": "p09-v1", "graph_version": settings.workflow_graph_version, "agent_config": {
        "providers": load_provider_config(settings.provider_config_path).model_dump(mode="json"),
        "policy": AgentPolicy(timeout_seconds=settings.run_timeout_seconds,
                              max_steps=settings.max_agent_steps).model_dump(mode="json"), "prompt_version": "p07-v1"}}
    if settings.workflow_graph_version == "supervisor-v2":
        from app.faults.source import source_snapshot
        value["agent_config"]["enterprise"] = source_snapshot(settings.enterprise_mock_fixture)
        value["agent_config"]["policy"]["version"] = "p08-v1"
        value["agent_config"]["prompt_version"] = "p08-v1"
    return value
