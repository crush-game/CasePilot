from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.domain.enums import TicketStatus
from app.domain.errors import AppError
from app.services.solutions import check_draft
from app.repositories.models import HumanAction, HumanTask, NodeRun, ProviderBudget
from app.services.workflow_common import append_event, latest_snapshot, save_snapshot, transition


def checkpoint_ref(snapshot):
    checkpoint_id = (snapshot.config or {}).get("configurable", {}).get("checkpoint_id")
    return {"checkpoint_id": checkpoint_id} if checkpoint_id else {}


def current_interrupt(snapshot):
    return next((value for task in snapshot.tasks for value in task.interrupts), None)


def project_nodes(ctx, snapshot):
    state = snapshot.values
    with Session(ctx.engine) as db:
        ticket, run, _ = ctx.fenced(db)
        for step in state.get("completed_steps", []):
            node_id = db.scalar(insert(NodeRun).values(
                run_id=run.id, logical_step_id=step["logical_step_id"], attempt=1,
                node_name=step["node_name"], duration_ms=step["duration_ms"], status=step["status"],
                input_refs={"case_version": step.get("case_version", state["case_version"])},
                output_refs={"data_source": "mock", **step.get("output_refs", {}),
                             "inference_mode": state.get("inference_mode", "mock")},
                usage_json={**step.get("usage", {"model_calls": 0}), "budget_epoch": step["epoch"]},
            ).on_conflict_do_nothing(constraint="uq_node_runs_step").returning(NodeRun.id))
            if node_id:
                append_event(db, ticket, "node.completed", {"node_name": step["node_name"], "node_run_id": str(node_id), "data_source": "mock"})
        run.checkpoint_ref = checkpoint_ref(snapshot)
        run.budget_json = {**run.budget_json, "steps": sum(step["epoch"] == ctx.epoch for step in state.get("completed_steps", [])),
                           "elapsed_seconds": ctx.elapsed(), "model_calls": sum(
                               step.get("usage", {}).get("model_calls", 0) for step in state.get("completed_steps", [])
                               if step["epoch"] == ctx.epoch), "data_source": "mock"}
        if run.budget_json.get("agent_provider_budget_id"):
            budget = db.get(ProviderBudget, UUID(run.budget_json["agent_provider_budget_id"]))
            run.budget_json = {**run.budget_json, "provider_calls": budget.calls_used, "token_exposure": budget.tokens_used,
                               "cost_exposure": float(budget.exposure_cost), "currency": budget.currency,
                               "inference_mode": state.get("inference_mode", "none")}
        db.commit()


def project_result(ctx, snapshot, failure_reason=None):
    state = snapshot.values or {}
    paused = current_interrupt(snapshot)
    complete = bool(state.get("complete") and not snapshot.next)
    if not paused and not complete and not failure_reason:
        return False
    with Session(ctx.engine) as db:
        ticket, run, task = ctx.fenced(db)
        ref = checkpoint_ref(snapshot)
        consumed = [UUID(value) for value in state.get("consumed_action_ids", [])]
        if consumed:
            actions = list(db.scalars(select(HumanAction).where(HumanAction.run_id == run.id, HumanAction.action_id.in_(consumed))))
            for action in actions:
                if action.consumed_at is None:
                    action.consumed_at = func.now()
                    action.consumed_checkpoint = ref.get("checkpoint_id")
                human = db.get(HumanTask, action.human_task_id)
                if human.status == "resuming":
                    human.status = "completed"
        previous = latest_snapshot(db, run.id)
        validated = None
        invalid_draft = False
        if complete and not paused and not failure_reason:
            try:
                validated = check_draft(db, ticket, run, {**previous, **state}, state.get("solution", {}))
            except AppError as exc:
                failure_reason = exc.code
                invalid_draft = True
        if paused or failure_reason:
            payload = {"reason_code": failure_reason, "missing_fields": [], "data_source": "mock"} if failure_reason else paused.value
            if invalid_draft:
                payload.update(requires_reinvestigation=True, evidence_refs=state.get("evidence_refs", []))
                if state.get("fault_report"):
                    payload["fault_report"] = state["fault_report"]
            pause_key = f"failure:{task.id}" if failure_reason else paused.id
            old_tasks = list(db.scalars(select(HumanTask).where(
                HumanTask.ticket_id == ticket.id, HumanTask.status.in_(["unclaimed", "claimed", "resuming"]),
                HumanTask.pause_key != pause_key,
            )))
            for old in old_tasks:
                old.status = "cancelled"
            db.flush()  # 部分唯一索引要求先关闭旧待办，再建立新的暂停待办。
            db.execute(insert(HumanTask).values(
                ticket_id=ticket.id, run_id=run.id, pause_key=pause_key,
                reason_code=payload["reason_code"], status="unclaimed", checkpoint_ref=ref, payload_json=payload,
            ).on_conflict_do_nothing(constraint="uq_human_tasks_pause"))
            transition(ticket, TicketStatus.WAITING_HUMAN)
            run.status, run.stop_reason = "paused", payload["reason_code"]
            append_event(db, ticket, "run.paused", {"pause_key": pause_key, **payload})
        else:
            transition(ticket, TicketStatus.PENDING_CONFIRMATION)
            run.status, run.stop_reason = "succeeded", None
            ticket.solution_json = validated
            append_event(db, ticket, "run.completed", {"data_source": "mock", "stop_reason": "solution_ready"})
        run.cancel_requested = False
        run.checkpoint_ref = ref
        run.budget_json = {**run.budget_json, "elapsed_seconds": ctx.elapsed(), "data_source": "mock"}
        projected = {**previous, **state, "request": previous["request"], "budget_epoch": ctx.epoch}
        if validated is not None:
            projected["solution"] = validated
        save_snapshot(db, ticket, run, projected)
        task.status, task.lease_token, task.lease_until = "succeeded", None, None
        db.commit()
    return True
