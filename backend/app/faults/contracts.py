from typing import Literal

from pydantic import Field

from app.agents.contracts import Finding, SubtaskResult, SupervisorDecision
from app.tools.contracts import Contract


class InvestigationDecision(SupervisorDecision):
    fault_domains: list[Literal["wifi", "ota"]] = Field(default_factory=list, max_length=2)


class FaultDecision(Contract):
    action: Literal["get_feedbacks", "download_log", "extract_log_window", "get_wifi_telemetry",
                    "diagnose_wifi", "analyze_domain", "expand_window", "finish", "human"]
    domain: Literal["wifi", "ota"] | None = None
    reason: str = Field(min_length=1, max_length=500)
    evidence_refs: list[str] = Field(max_length=16)
    data_source: Literal["mock"]


class CandidateCause(Contract):
    hypothesis: str = Field(min_length=1, max_length=500)
    supporting_refs: list[str] = Field(min_length=1, max_length=8)
    contradicting_refs: list[str] = Field(max_length=8)
    required_verification: str = Field(min_length=1, max_length=500)
    confirmation: Literal["unconfirmed"] = "unconfirmed"


class FaultAnalysis(Contract):
    domain: Literal["wifi", "ota"]
    findings: list[Finding] = Field(min_length=1, max_length=4)
    candidate_causes: list[CandidateCause] = Field(max_length=2)
    limitations: list[str] = Field(min_length=1, max_length=6)
    evidence_refs: list[str] = Field(min_length=1, max_length=16)
    data_source: Literal["mock"]


class FaultResult(SubtaskResult):
    inspected_domains: list[str] = Field(default_factory=list)
    candidate_causes: list[CandidateCause] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    viewed_range: dict = Field(default_factory=dict)
    source_kind: Literal["detailed_log", "telemetry", "none"] = "none"


class FaultToolArgs(Contract):
    feedback_ref: str | None = None
    artifact_ref: str | None = None
    window_kind: Literal["initial", "expanded"] = "initial"


class FaultObservation(Contract):
    status: Literal["success", "no_data", "needs_human", "error"]
    data_source: Literal["mock"] = "mock"
    data_refs: list[str] = Field(default_factory=list)
    data: dict = Field(default_factory=dict)
    error_code: str | None = None
    retryable: bool = False
    source: dict
    fetched_at: str
