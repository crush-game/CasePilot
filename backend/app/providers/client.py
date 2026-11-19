import asyncio
from collections.abc import Awaitable, Callable
import json
import time
from typing import Literal, TypeVar

from pydantic import Field, ValidationError

from app.tools.contracts import Contract


Role = Literal["parse", "supervisor", "solution", "domain"]


class ModelProfile(Contract):
    provider: str = "mock"
    model: str = "deterministic-v1"
    timeout_seconds: float = Field(default=5.0, gt=0, le=300)


class ModelRequest(Contract):
    role: Role
    input: dict
    allowed_evidence_refs: list[str]
    data_source: Literal["mock", "real"] = "mock"


class ModelUsage(Contract):
    provider: str
    model: str
    role: Role
    model_calls: int = 1
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    simulated: bool = True
    duration_ms: int
    inference_mode: Literal["mock", "contract", "real"] = "mock"
    currency: str | None = None
    tokens_source: str = "mock"
    price_version: str | None = None
    call_ids: list[str] = Field(default_factory=list)


class SolutionDraft(Contract):
    internal_plan: str
    reply_draft: str
    data_source: Literal["mock", "real"]
    evidence_refs: list[str]
    reviewed: Literal[False] = False


class DomainDraft(Contract):
    findings: list[str]
    limitations: list[str]
    data_source: Literal["mock", "real"]
    evidence_refs: list[str]


class ModelFailure(Exception):
    def __init__(self, code: str, usage=None):
        self.code, self.usage = code, usage
        super().__init__(code)


async def mock_transport(request: ModelRequest) -> str:
    # 固定测试响应不推理根因，不读取场景编号、隐藏标签或供应商配置。
    common = {"data_source": "mock", "evidence_refs": request.allowed_evidence_refs}
    if request.role == "solution":
        return json.dumps({**common,
            "internal_plan": "【模拟方案】核对设备与故障时间，按测试流程检查连接并记录验证结果。",
            "reply_draft": "【模拟回复草稿】请按确认的检查步骤验证设备状态，并反馈是否解决。",
            "reviewed": False}, ensure_ascii=False)
    if request.role == "domain":
        return json.dumps({**common, "findings": ["【模拟分析】所选片段仅供人工核对，不确定根因。"],
                           "limitations": ["确定性 Mock 输出；时间相关不代表因果，未验证模型诊断效果。"]}, ensure_ascii=False)
    raise ModelFailure("ROLE_NOT_IMPLEMENTED")


T = TypeVar("T", bound=Contract)


class ModelClient:
    def __init__(self, profiles: dict[str, ModelProfile] | None = None,
                 transport: Callable[[ModelRequest], Awaitable[str]] | None = None, *, provider_session=None):
        self.profiles = profiles or {}
        self.transport = transport or mock_transport
        self.provider_session = provider_session

    async def acomplete(self, request: ModelRequest, output_schema: type[T]) -> tuple[T, ModelUsage]:
        profile = self.profiles.get(request.role, ModelProfile())
        if profile.provider == "openai_compatible":
            return await self._remote(request, output_schema, profile)
        if profile.provider != "mock" or profile.model != "deterministic-v1" or request.data_source != "mock":
            raise ModelFailure("PROVIDER_NOT_CONFIGURED")
        started = time.monotonic()
        try:
            async with asyncio.timeout(profile.timeout_seconds):
                raw = await self.transport(request)
        except TimeoutError:
            raise ModelFailure("MODEL_TIMEOUT") from None
        except ModelFailure:
            raise
        except Exception:
            raise ModelFailure("MODEL_FAILED") from None
        try:
            output = output_schema.model_validate_json(raw, strict=True)
        except (ValidationError, ValueError, TypeError):
            raise ModelFailure("INVALID_MODEL_OUTPUT") from None
        values = output.model_dump()
        if values.get("data_source") != "mock" or not set(values.get("evidence_refs", [])) <= set(request.allowed_evidence_refs):
            raise ModelFailure("UNTRUSTED_MODEL_EVIDENCE")
        return output, ModelUsage(provider=profile.provider, model=profile.model, role=request.role,
                                  duration_ms=int((time.monotonic() - started) * 1000))

    async def _remote(self, request, output_schema, profile):
        from app.providers.ledger import ProviderFailure
        session = self.provider_session
        if session is None:
            raise ModelFailure("PROVIDER_AUDIT_REQUIRED")
        started, attempts = time.monotonic(), []
        for repair in range(2):
            try:
                raw, measured = await session.achat(request, output_schema, profile.model, repair=bool(repair))
            except ProviderFailure as exc:
                if exc.usage:
                    attempts.extend(exc.usage.get("attempts", [exc.usage]))
                raise ModelFailure(exc.code, self._usage(session, request.role, profile.model, started, attempts)) from None
            attempts.extend(measured["attempts"])
            try:
                output = output_schema.model_validate_json(raw, strict=True)
            except (ValidationError, ValueError, TypeError):
                session.reject(measured["call_id"], "INVALID_MODEL_OUTPUT")
                if not repair:
                    continue
                raise ModelFailure("INVALID_MODEL_OUTPUT", self._usage(session, request.role, profile.model, started, attempts)) from None
            values = output.model_dump()
            if values.get("data_source") != request.data_source or not set(values.get("evidence_refs", [])) <= set(request.allowed_evidence_refs):
                session.reject(measured["call_id"], "UNTRUSTED_MODEL_EVIDENCE")
                raise ModelFailure("UNTRUSTED_MODEL_EVIDENCE", self._usage(session, request.role, profile.model, started, attempts))
            return output, self._usage(session, request.role, profile.model, started, attempts)

    @staticmethod
    def _usage(session, role, model, started, attempts):
        total = lambda field: sum(row[field] for row in attempts) if attempts and all(row[field] is not None for row in attempts) else None
        return ModelUsage(provider="openai_compatible", model=model, role=role, model_calls=len(attempts),
            input_tokens=total("input_tokens"), output_tokens=total("output_tokens"), cost=total("cost"),
            simulated=session.mode != "real", inference_mode=session.mode, currency=session.config.chat_roles.get(role, session.config.chat).currency,
            tokens_source="reported" if attempts and all(row["tokens_source"] == "reported" for row in attempts) else "estimated_upper_bound",
            price_version=session.config.chat_roles.get(role, session.config.chat).price_version,
            call_ids=[row["call_id"] for row in attempts], duration_ms=int((time.monotonic() - started) * 1000))

    def complete(self, request: ModelRequest, output_schema: type[T]) -> tuple[T, ModelUsage]:
        # Worker 是同步入口；异步调用方使用 acomplete，避免嵌套事件循环。
        return asyncio.run(self.acomplete(request, output_schema))
