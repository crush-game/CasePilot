from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.repositories.models import ProviderBudget, ProviderCall
from app.services.tickets import digest


class ProviderFailure(Exception):
    def __init__(self, code, *, usage=None):
        self.code, self.usage = code, usage
        super().__init__(code)


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_CEILING)


def cost_for(profile, input_tokens, output_tokens):
    if input_tokens is None or output_tokens is None and profile.output_price_per_million:
        return None
    return money((Decimal(input_tokens) * Decimal(str(profile.input_price_per_million))
                  + Decimal(output_tokens or 0) * Decimal(str(profile.output_price_per_million))) / Decimal(1000000))


def create_budget(engine, *, scope, max_cost=Decimal("5"), currency="CNY", max_calls=60, max_tokens=500000, seconds=600):
    amount = Decimal(str(max_cost))
    if not amount.is_finite() or not 0 < amount <= 1000 or not 1 <= max_calls <= 1000 or not 1 <= max_tokens <= 5000000 or not 1 <= seconds <= 3600:
        raise ProviderFailure("INVALID_PROVIDER_BUDGET")
    amount = money(amount)
    with Session(engine, expire_on_commit=False) as db:
        now = db.scalar(select(func.clock_timestamp()))
        budget = ProviderBudget(scope=scope[:120], max_calls=max_calls, max_tokens=max_tokens, max_cost=amount,
                                currency=currency, expires_at=now + timedelta(seconds=seconds))
        db.add(budget)
        db.commit()
        return budget.id


def reserve(engine, budget_id, operation, profile, payload, input_bound, output_bound, mode):
    if input_bound > profile.max_input_tokens:
        raise ProviderFailure("PROVIDER_INPUT_LIMIT")
    reserved_cost = cost_for(profile, input_bound, output_bound)
    with Session(engine, expire_on_commit=False) as db:
        budget = db.scalar(select(ProviderBudget).where(ProviderBudget.id == budget_id).with_for_update())
        now = db.scalar(select(func.clock_timestamp()))
        if budget is None or budget.expires_at <= now:
            raise ProviderFailure("PROVIDER_BUDGET_EXPIRED")
        if budget.currency != profile.currency:
            raise ProviderFailure("PROVIDER_CURRENCY_MISMATCH")
        bound = input_bound + output_bound
        if (budget.calls_used >= budget.max_calls or budget.tokens_used + bound > budget.max_tokens
                or budget.exposure_cost + reserved_cost > budget.max_cost):
            raise ProviderFailure("PROVIDER_BUDGET_EXHAUSTED")
        call = ProviderCall(budget_id=budget.id, operation=operation, inference_mode=mode,
            profile_json=profile.model_dump(mode="json"), request_hash=digest(payload),
            reserved_tokens=bound, reserved_cost=reserved_cost, usage_json={"reservation_sequence": budget.calls_used + 1})
        db.add(call)
        budget.calls_used += 1
        budget.tokens_used += bound
        budget.exposure_cost += reserved_cost
        db.commit()
        return call.id, max(0.01, (budget.expires_at - now).total_seconds())


def settle(engine, call_id, profile, *, input_tokens=None, output_tokens=None, error_code=None,
           duration_ms=0, response_hash=None, request_id=None, served_model=None):
    with Session(engine) as db:
        record = db.get(ProviderCall, call_id)
        budget = db.scalar(select(ProviderBudget).where(ProviderBudget.id == record.budget_id).with_for_update())
        call = db.scalar(select(ProviderCall).where(ProviderCall.id == call_id).with_for_update().execution_options(populate_existing=True))
        if call.status != "reserved":
            raise ProviderFailure("PROVIDER_CALL_ALREADY_SETTLED")
        measured = input_tokens is not None and output_tokens is not None
        cost = cost_for(profile, input_tokens, output_tokens)
        if measured:
            budget.tokens_used += input_tokens + output_tokens - call.reserved_tokens
        if cost is not None:
            budget.exposure_cost += cost - call.reserved_cost
        overrun = budget.tokens_used > budget.max_tokens or budget.exposure_cost > budget.max_cost
        error_code = "PROVIDER_BUDGET_OVERRUN" if overrun else error_code
        usage = {"call_id": str(call.id), "provider": "openai_compatible", "model": profile.model,
            "inference_mode": call.inference_mode, "simulated": call.inference_mode != "real",
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "tokens_source": "reported" if measured else "estimated_upper_bound", "reserved_tokens": call.reserved_tokens,
            "cost": float(cost) if cost is not None else None, "currency": profile.currency,
            "cost_source": "configured_price" if cost is not None else "unknown",
            "price_version": profile.price_version, "duration_ms": duration_ms, "error_code": error_code}
        usage["served_model"] = served_model
        usage["reservation_sequence"] = call.usage_json.get("reservation_sequence")
        call.status, call.error_code = "failed" if error_code else "succeeded", error_code
        call.usage_json, call.duration_ms = usage, duration_ms
        call.response_hash, call.provider_request_id = response_hash, request_id
        db.commit()
    if overrun:
        raise ProviderFailure("PROVIDER_BUDGET_OVERRUN", usage=usage)
    return usage


def invalidate(engine, call_id: UUID, code):
    with Session(engine) as db:
        call = db.scalar(select(ProviderCall).where(ProviderCall.id == call_id).with_for_update())
        call.status, call.error_code = "failed", code
        call.usage_json = {**call.usage_json, "error_code": code}
        db.commit()


def budget_report(engine, budget_id):
    with Session(engine) as db:
        budget = db.get(ProviderBudget, budget_id)
        calls = list(db.scalars(select(ProviderCall).where(ProviderCall.budget_id == budget_id).order_by(
            ProviderCall.usage_json["reservation_sequence"].as_integer(), ProviderCall.created_at, ProviderCall.id)))
        return {"budget_id": str(budget.id), "currency": budget.currency, "max_cost": float(budget.max_cost),
            "exposure_upper_bound": float(budget.exposure_cost), "calls_used": budget.calls_used,
            "token_exposure": budget.tokens_used, "calls": [{"id": str(row.id), "operation": row.operation,
                "status": row.status, "request_hash": row.request_hash, "response_hash": row.response_hash,
                "provider_request_id": row.provider_request_id, "usage": row.usage_json} for row in calls]}
