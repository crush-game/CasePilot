"""P07 的持久逻辑动作与受控 I/O；外部请求不持业务事务锁。"""

from decimal import Decimal
import json
import math
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.contracts import AgentPolicy, SCOPE_FIELDS
from app.config import get_settings
from app.domain.errors import AppError
from app.knowledge.index import get_citation, search
from app.knowledge.schemas import KnowledgeScope, SearchQuery
from app.providers.client import ModelClient, ModelFailure, ModelProfile, ModelRequest
from app.providers.configuration import ProviderConfig
from app.providers.ledger import ProviderFailure, create_budget
from app.providers.remote import ProviderSession, clean_input
from app.repositories.models import ProviderBudget, ToolExecution
from app.services.tickets import digest
from app.workers.faults import failpoint


class AgentIO:
    def __init__(self, ctx):
        self.ctx = ctx
        self.session = None

    def guard(self, state):
        reason = self.ctx.control(state)
        if reason:
            raise ProviderFailure(reason)

    def session_for(self, state):
        if self.session is not None:
            return self.session
        config = ProviderConfig.model_validate(state["agent_config"]["providers"])
        policy = AgentPolicy.model_validate(state["agent_config"]["policy"])
        override = getattr(self.ctx, "provider_session", None)
        if override and override.config != config:
            raise ProviderFailure("MODEL_PROFILE_MISMATCH")
        with Session(self.ctx.engine) as db:
            _, run, _ = self.ctx.fenced(db)
            budget = run.budget_json
            identifier = budget.get("agent_provider_budget_id")
            if not identifier:
                previous = {UUID(row["agent_provider_budget_id"]) for row in budget.get("history", [])
                            if row.get("agent_provider_budget_id")}
                records = list(db.scalars(select(ProviderBudget).where(ProviderBudget.id.in_(previous))))
                cost = min(Decimal(str(policy.max_cost)), Decimal(str(policy.max_run_cost)) - sum(row.exposure_cost for row in records))
                calls = min(policy.max_model_calls, policy.max_run_calls - sum(row.calls_used for row in records))
                tokens = min(policy.max_tokens, policy.max_run_tokens - sum(row.tokens_used for row in records))
                seconds = math.floor(policy.timeout_seconds - self.ctx.elapsed())
                if cost <= 0 or calls <= 0 or tokens <= 0 or seconds < 1:
                    raise ProviderFailure("BUDGET_EXHAUSTED")
                identifier = override.budget_id if override else create_budget(self.ctx.engine,
                    scope=f"{self.ctx.run_id}:{self.ctx.epoch}", max_cost=cost, currency=config.chat.currency,
                    max_calls=calls, max_tokens=tokens, seconds=min(seconds, 3600))
                budget = {**budget, "agent_provider_budget_id": str(identifier), "agent_tools_used": 0}
                run.budget_json = budget
                db.commit()
        if override and str(override.budget_id) != str(identifier):
            raise ProviderFailure("PROVIDER_BUDGET_MISMATCH")
        self.session = override or ProviderSession(self.ctx.engine, UUID(str(identifier)), config, get_settings().provider_api_key)
        self.session.before_attempt = lambda: self.guard(self.current_state)
        return self.session

    @staticmethod
    def scope(state):
        return {name: state["request"].get(name) for name in SCOPE_FIELDS}

    def action(self, state, name, payload, operation, *, tool=False):
        self.guard(state)
        self.current_state = state
        policy = AgentPolicy.model_validate(state["agent_config"]["policy"])
        action_id = uuid5(self.ctx.run_id, f"p07:{self.ctx.epoch}:{len(state.get('completed_steps', []))}:{name}")
        fingerprint = digest({"payload": clean_input(payload), "config": state["agent_config"]})
        with Session(self.ctx.engine) as db:
            _, run, _ = self.ctx.fenced(db)
            old = db.scalar(select(ToolExecution).where(ToolExecution.run_id == self.ctx.run_id,
                                                       ToolExecution.logical_action_id == action_id))
            if old:
                if old.args_hash != fingerprint:
                    raise ProviderFailure("LOGICAL_ACTION_MISMATCH")
                if old.status == "running":
                    raise ProviderFailure("ACTION_OUTCOME_UNKNOWN")
                if old.status == "failed":
                    raise ModelFailure(old.error_code, old.result_refs.get("usage"))
                return old.result_refs
            if tool and run.budget_json.get("agent_tools_used", 0) >= policy.max_tools:
                raise ProviderFailure("TOOL_BUDGET_EXHAUSTED")
            if tool:
                run.budget_json = {**run.budget_json, "agent_tools_used": run.budget_json.get("agent_tools_used", 0) + 1}
            db.add(ToolExecution(run_id=self.ctx.run_id, logical_action_id=action_id, tool_name=name,
                                args_hash=fingerprint, status="running", result_refs={}))
            db.commit()
        failpoint("before_agent_request")
        failure = None
        try:
            value, usage = operation()
        except (ModelFailure, ProviderFailure, AppError) as exc:
            failure = exc.code
            raw = getattr(exc, "usage", None)
            usage = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw or {"model_calls": 0}
            value = None
        self.ctx.control(state, allow_pause=True)
        result = {"value": value, "usage": usage, "action_id": str(action_id)}
        with Session(self.ctx.engine) as db:
            self.ctx.fenced(db)
            row = db.scalar(select(ToolExecution).where(ToolExecution.run_id == self.ctx.run_id,
                                                        ToolExecution.logical_action_id == action_id))
            row.status, row.error_code = "failed" if failure else "succeeded", failure
            row.result_refs = result
            db.commit()
        failpoint("after_agent_action_write")
        if name == "search_knowledge":
            failpoint("after_agent_search_write")
        self.guard(state)
        if failure:
            raise ModelFailure(failure, usage)
        return result

    def model(self, state, name, schema, instruction, observation, refs):
        role = "parse" if name == "parse_request" else "solution" if name == "generate_solution" else "supervisor"
        request = ModelRequest(role=role, input=clean_input(observation), allowed_evidence_refs=refs,
                               task_instruction=instruction)
        def execute():
            session = self.session_for(state)
            profile = session.config.chat_roles.get(role, session.config.chat)
            selected = request
            if "evidence" in observation:
                fields = {"ref", "title", "text", "doc_key", "document_version", "heading_path", "metadata",
                          "product_scope", "firmware_versions", "regions", "channels", "effective_from", "effective_to"}
                if schema.__name__ == "SupervisorDecision":
                    fields -= {"text", "metadata"}  # 父编排使用结构化发现，原文由检查和生成节点按引用取得。
                evidence = [{key: value for key, value in row.items() if key in fields} for row in observation["evidence"]]
                omitted = []
                while True:
                    sent_refs = [row["ref"] for row in evidence]
                    selected = request.model_copy(update={"input": {**request.input, "evidence": evidence,
                        "context_coverage": {"omitted_refs": omitted}}, "allowed_evidence_refs": sent_refs})
                    _, payload = session.chat_payload(selected, schema, profile.model, repair=True)
                    if len(json.dumps(payload, ensure_ascii=False).encode()) + 512 <= profile.max_input_tokens:
                        break
                    if not evidence:
                        raise ProviderFailure("PROVIDER_INPUT_LIMIT")
                    omitted.insert(0, evidence.pop()["ref"])
                if refs and not sent_refs:
                    raise ProviderFailure("PROVIDER_INPUT_LIMIT")
            client = ModelClient({role: ModelProfile(provider="openai_compatible", model=profile.model)}, provider_session=session)
            value, usage = client.complete(selected, schema)
            return value.model_dump(mode="json"), {**usage.model_dump(mode="json"),
                "context_refs": selected.allowed_evidence_refs,
                "omitted_refs": selected.input.get("context_coverage", {}).get("omitted_refs", [])}
        return self.action(state, "model:" + name, request.model_dump(mode="json"), execute)

    def retrieve(self, state, query):
        args = SearchQuery(query=query, **self.scope(state), retrieval_mode="hybrid", rerank=True)
        def execute():
            with Session(self.ctx.engine) as db:
                result = search(db, args, self.session_for(state)).model_dump(mode="json")
            calls = result["provider_usage"]
            return result, {"model_calls": len(calls), "provider_calls": calls}
        return self.action(state, "search_knowledge", args.model_dump(mode="json"), execute, tool=True)

    def citations(self, state, refs):
        values = []
        with Session(self.ctx.engine) as db:
            for ref in refs:
                try:
                    identifier = UUID(ref.removeprefix("kb:"))
                except ValueError:
                    raise ProviderFailure("UNTRUSTED_MODEL_EVIDENCE") from None
                value = get_citation(db, identifier, KnowledgeScope(**self.scope(state)))
                if not value.usable:
                    raise ProviderFailure("EVIDENCE_NOT_APPLICABLE")
                values.append(value.model_dump(mode="json"))
        return values

    def context(self, state, refs):
        allowed = {row["ref"]: row for row in state.get("knowledge_candidates", [])}
        if not refs or not set(refs) <= set(allowed):
            raise ProviderFailure("UNTRUSTED_CONTEXT_REQUEST")
        def execute():
            nearby = []
            for ref in refs:
                fresh = self.citations(state, [ref])[0]
                nearby.extend(value for key, value in fresh["metadata"].items() if key in {"previous_ref", "next_ref"} and value)
            values = self.citations(state, list(dict.fromkeys(nearby)))
            return values, {"model_calls": 0}
        return self.action(state, "get_knowledge_context", {"refs": refs, "scope": self.scope(state)}, execute, tool=True)
