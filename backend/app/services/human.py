from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.api.schemas import HumanTaskView
from app.config import get_settings
from app.domain.enums import HumanTaskStatus, RunStatus, TicketStatus
from app.domain.errors import AppError
from app.domain.states import TERMINAL_STATUSES
from app.repositories.models import ExecutionTask, HumanAction, HumanTask, Run, Ticket, TicketFact
from app.services.experiences import enqueue_candidate
from app.services.solutions import check_draft
from app.services.tickets import reserve_request
from app.services.workflow_common import (
    append_event, audit_action, latest_snapshot, lock_ticket, require_run_lock,
    save_snapshot, transition,
)


OPEN_HUMAN_STATUSES = {"unclaimed", "claimed", "resuming"}


def action_result(ticket, human_task_id=None):
    return {"ticket_id": str(ticket.id), "status": ticket.status, "version": ticket.version,
            "run_id": str(ticket.active_run_id) if ticket.active_run_id else None,
            "human_task_id": str(human_task_id) if human_task_id else None}


def begin_action(db, actor, operation, body):
    return reserve_request(db, actor.id, operation, str(body.action_id), body.model_dump(mode="json"))


def finish_action(db, record, ticket, actor, body, operation, human_task_id=None):
    result = action_result(ticket, human_task_id)
    record.response_ref = result
    audit_action(db, ticket, actor.id, body, operation, result)
    db.commit()
    return result


def get_human_task(db: Session, task_id: UUID):
    task = db.get(HumanTask, task_id)
    if task is None:
        raise AppError(404, "HUMAN_TASK_NOT_FOUND", "人工待办不存在")
    return task


def human_view(task, ticket):
    return HumanTaskView(**{name: getattr(task, name) for name in HumanTaskView.model_fields
                            if name not in {"expected_version", "priority"}},
                         expected_version=ticket.version, priority=ticket.priority)


def claim(db: Session, actor, task_id: UUID, body):
    operation = f"human.claim:{task_id}"
    record, replay = begin_action(db, actor, operation, body)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    task = get_human_task(db, task_id)
    ticket = lock_ticket(db, task.ticket_id, body.expected_version)
    require_run_lock(db, task.run_id)
    db.refresh(task)
    if ticket.status != TicketStatus.WAITING_HUMAN or task.status not in {"unclaimed", "claimed"}:
        raise AppError(409, "INVALID_STATE", "待办当前不能认领")
    if task.assignee_id not in {None, actor.id}:
        raise AppError(409, "ALREADY_CLAIMED", "待办已被其他业务人员认领")
    if task.status == "unclaimed":
        task.assignee_id, task.status = actor.id, HumanTaskStatus.CLAIMED
        ticket.assignee_id = actor.id
        ticket.version += 1
        ticket.updated_at = func.now()
        run = db.get(Run, task.run_id)
        save_snapshot(db, ticket, run, latest_snapshot(db, run.id))
        append_event(db, ticket, "human.claimed", {"human_task_id": str(task.id), "actor_id": str(actor.id)})
    return finish_action(db, record, ticket, actor, body, "human.claim", task.id)


def apply_facts(db: Session, ticket, run, state: dict, patch: dict, actor, action_id, allow_replace=False):
    request = {**state["request"]}
    for field, value in patch.items():
        if field == "occurred_at_precision":
            continue
        existing = request.get(field)
        if existing is not None and existing != value and not allow_replace:
            raise AppError(409, "REINVESTIGATION_REQUIRED", "修正已分析的关键事实请使用重新调查")
        request[field] = value
        db.add(TicketFact(
            ticket_id=ticket.id, field=field, value_json={"value": value}, source_type="human",
            source_ref=str(action_id), fact_version=ticket.version, actor_id=actor.id,
        ))
        if field == "device_ref":
            ticket.device_ref = value
        elif field == "occurred_at":
            ticket.occurred_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
            ticket.occurred_at_original = value
            ticket.occurred_at_precision = patch.get("occurred_at_precision", "second")
            request["occurred_at_precision"] = ticket.occurred_at_precision
    return {**state, "request": request}


def resume(db: Session, actor, task_id: UUID, body):
    operation = f"human.resume:{task_id}"
    record, replay = begin_action(db, actor, operation, body)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    task = get_human_task(db, task_id)
    ticket = lock_ticket(db, task.ticket_id, body.expected_version)
    require_run_lock(db, task.run_id)
    db.refresh(task)
    if ticket.status != TicketStatus.WAITING_HUMAN or task.status != "claimed":
        raise AppError(409, "INVALID_STATE", "请先认领仍开放的待办")
    if task.assignee_id != actor.id:
        raise AppError(403, "NOT_TASK_OWNER", "只有认领人可以恢复此待办")
    run = db.get(Run, task.run_id)
    if run.status != RunStatus.PAUSED or ticket.active_run_id != run.id:
        raise AppError(409, "INVALID_STATE", "待办对应运行已失效")
    if (run.graph_version not in {"mock-v1", "supervisor-v1", "supervisor-v2"} or not task.checkpoint_ref.get("checkpoint_id")
            or task.payload_json.get("requires_reinvestigation")
            or task.reason_code in {"CHECKPOINT_MISSING", "PAUSE_MISMATCH", "GRAPH_VERSION_UNSUPPORTED"}):
        raise AppError(409, "REINVESTIGATION_REQUIRED", "检查点不可直接恢复，请人工处理或重新调查")
    state = latest_snapshot(db, run.id)
    epoch = state.get("budget_epoch", 0) + 1
    if epoch >= get_settings().max_budget_epochs:
        raise AppError(409, "BUDGET_EPOCH_LIMIT", "已达到跨轮次上限，请人工处理或结案")
    patch = body.facts_patch.model_dump(mode="json", exclude_unset=True)
    if task.reason_code == "MISSING_FACTS" and not patch:
        raise AppError(422, "FACTS_REQUIRED", "请补充待确认信息后再恢复")
    if run.graph_version == "supervisor-v2" and patch:
        from app.faults.source import CONTEXT_FIELDS
        from app.repositories.models import LogArtifact
        if set(patch).intersection(CONTEXT_FIELDS) and db.scalar(select(LogArtifact.id).where(LogArtifact.run_id == run.id).limit(1)):
            raise AppError(409, "REINVESTIGATION_REQUIRED", "已读取日志后补充或修正关联事实，请重新调查以保留原证据范围")
    transition(ticket, TicketStatus.QUEUED)
    state = apply_facts(db, ticket, run, state, patch, actor, body.action_id)
    if task.reason_code == "FEEDBACK_SELECTION_REQUIRED":
        if run.graph_version != "supervisor-v2" or not body.selected_feedback_ref:
            raise AppError(422, "FEEDBACK_SELECTION_REQUIRED", "请选择属于本次故障的一条反馈")
        offered = {row["record_id"] for row in task.payload_json.get("feedback_candidates", [])}
        if body.selected_feedback_ref not in offered:
            raise AppError(422, "FEEDBACK_SCOPE_MISMATCH", "选择的反馈不在当前候选范围")
        from app.faults.source import require_feedback
        from app.providers.ledger import ProviderFailure
        try:
            require_feedback(state["agent_config"]["enterprise"], ticket.customer_email, state["request"], body.selected_feedback_ref)
        except ProviderFailure as exc:
            raise AppError(409, exc.code, "反馈来源或适用范围已变化，请核对后重新调查") from None
        state["selected_feedback_ref"] = body.selected_feedback_ref
    elif body.selected_feedback_ref is not None:
        raise AppError(422, "FEEDBACK_SELECTION_UNSUPPORTED", "当前待办不接受反馈选择")
    payload = {"action_id": str(body.action_id), "facts_patch": patch, "budget_epoch": epoch,
               "human_task_id": str(task.id), "pause_key": task.pause_key}
    if body.selected_feedback_ref is not None:
        payload["selected_feedback_ref"] = body.selected_feedback_ref
    run.status, task.status = RunStatus.QUEUED, HumanTaskStatus.RESUMING
    run.cancel_requested = False
    save_snapshot(db, ticket, run, state)
    db.add(HumanAction(action_id=body.action_id, human_task_id=task.id, run_id=run.id,
                       actor_id=actor.id, expected_version=body.expected_version, request_json=payload))
    db.add(ExecutionTask(run_id=run.id, kind="resume", action_id=body.action_id, payload_json=payload))
    append_event(db, ticket, "human.resume_queued", {"action_id": str(body.action_id), "human_task_id": str(task.id)})
    return finish_action(db, record, ticket, actor, body, "human.resume", task.id)


def takeover(db: Session, actor, ticket_id: UUID, body):
    record, replay = begin_action(db, actor, f"tickets.takeover:{ticket_id}", body)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket = lock_ticket(db, ticket_id, body.expected_version)
    if ticket.status not in {TicketStatus.QUEUED, TicketStatus.RUNNING}:
        raise AppError(409, "INVALID_STATE", "当前工单不需要请求运行停止")
    run = db.get(Run, ticket.active_run_id)
    run.cancel_requested, run.stop_reason = True, "TAKEOVER_REQUESTED"
    ticket.version += 1
    ticket.updated_at = func.now()
    save_snapshot(db, ticket, run, latest_snapshot(db, run.id))
    # 撤销旧执行权，但不绕过其仍持有的 run 锁；由 Worker/对账完成实际暂停。
    db.execute(update(ExecutionTask).where(ExecutionTask.run_id == run.id, ExecutionTask.status == "running")
               .values(lease_token=None, lease_until=func.now()))
    append_event(db, ticket, "run.stop_requested", {"reason": body.reason, "actor_id": str(actor.id)})
    return finish_action(db, record, ticket, actor, body, "tickets.takeover")


def close(db: Session, actor, ticket_id: UUID, body, *, confirmation="human_verified"):
    operation = "tickets.close" if confirmation == "human_verified" else "tickets.customer_confirmed"
    payload = body.model_dump(mode="json")
    if body.verified_steps is None:
        payload.pop("verified_steps")
    record, replay = reserve_request(db, actor.id, f"tickets.close:{ticket_id}", str(body.action_id), payload)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket = lock_ticket(db, ticket_id, body.expected_version)
    if ticket.status in TERMINAL_STATUSES or ticket.status == TicketStatus.RUNNING:
        raise AppError(409, "INVALID_STATE", "运行中请先接管，终态工单不能重复结案")
    run = db.get(Run, ticket.active_run_id) if ticket.active_run_id else None
    if run:
        require_run_lock(db, run.id)
    tasks = list(db.scalars(select(HumanTask).where(HumanTask.ticket_id == ticket.id, HumanTask.status.in_(OPEN_HUMAN_STATUSES))))
    if any(task.assignee_id not in {None, actor.id} for task in tasks):
        raise AppError(403, "NOT_TASK_OWNER", "此工单由其他业务人员接管")
    if any(task.status == "unclaimed" for task in tasks):
        raise AppError(409, "CLAIM_REQUIRED", "请先认领人工待办再结案")
    transition(ticket, TicketStatus.RESOLVED if body.outcome == "resolved" else TicketStatus.CLOSED_UNRESOLVED)
    ticket.result_json = {"outcome": body.outcome, "reason": body.reason, "source": "human",
                          "actor_id": str(actor.id), "data_source": "mock"}
    for task in tasks:
        task.status = HumanTaskStatus.COMPLETED if body.outcome == "resolved" else HumanTaskStatus.CANCELLED
    if run:
        run.cancel_requested = False
        if run.status in {"queued", "running", "paused"}:
            run.status, run.stop_reason = RunStatus.SUPERSEDED, "MANUALLY_CLOSED"
        db.execute(update(ExecutionTask).where(ExecutionTask.run_id == run.id, ExecutionTask.status.in_(["queued", "running"]))
                   .values(status="cancelled", lease_token=None, lease_until=None))
    if body.outcome == "resolved":
        ticket.result_json = {**ticket.result_json, "confirmation": confirmation, "verified_steps": body.verified_steps}
        enqueue_candidate(db, ticket, run, body.action_id)
    append_event(db, ticket, "ticket.closed", ticket.result_json)
    ticket.active_run_id = None
    return finish_action(db, record, ticket, actor, body, operation)


def review(db: Session, actor, ticket_id: UUID, body):
    record, replay = begin_action(db, actor, f"tickets.review:{ticket_id}", body)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket = lock_ticket(db, ticket_id, body.expected_version)
    if ticket.status != TicketStatus.PENDING_CONFIRMATION:
        raise AppError(409, "INVALID_STATE", "当前没有待审核方案")
    value = {**ticket.solution_json, "reviewed": body.decision == "approve"}
    if body.reply_draft is not None:
        value["reply_draft"] = body.reply_draft
    if body.decision == "approve":
        run = db.get(Run, ticket.active_run_id)
        value = check_draft(db, ticket, run, latest_snapshot(db, run.id), value)
    ticket.solution_json = value
    ticket.version += 1
    ticket.updated_at = func.now()
    append_event(db, ticket, "solution.reviewed", {"decision": body.decision, "actor_id": str(actor.id)})
    return finish_action(db, record, ticket, actor, body, "tickets.review")


def reinvestigate(db: Session, actor, ticket_id: UUID, body):
    record, replay = begin_action(db, actor, f"tickets.reinvestigate:{ticket_id}", body)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket = lock_ticket(db, ticket_id, body.expected_version)
    if ticket.status not in {TicketStatus.WAITING_HUMAN, TicketStatus.PENDING_CONFIRMATION, TicketStatus.WAITING_CUSTOMER}:
        raise AppError(409, "INVALID_STATE", "当前不能重新调查，请先停止运行")
    old = db.get(Run, ticket.active_run_id)
    require_run_lock(db, old.id)
    open_tasks = list(db.scalars(select(HumanTask).where(HumanTask.ticket_id == ticket.id, HumanTask.status.in_(OPEN_HUMAN_STATUSES))))
    if any(task.assignee_id not in {None, actor.id} for task in open_tasks):
        raise AppError(403, "NOT_TASK_OWNER", "此工单由其他业务人员接管")
    state = latest_snapshot(db, old.id)
    old.status, old.cancel_requested = RunStatus.SUPERSEDED, False
    for task in open_tasks:
        task.status = HumanTaskStatus.CANCELLED
    db.flush()  # 先释放活动 run 部分唯一索引，再创建新 run。
    transition(ticket, TicketStatus.QUEUED)
    new_id = uuid4()
    from app.agents.contracts import configuration_snapshot
    execution = configuration_snapshot()
    run = Run(id=new_id, ticket_id=ticket.id, thread_id=str(new_id),
              graph_version=execution.get("graph_version", "mock-v1"), case_version=ticket.version)
    db.add(run)
    db.flush()
    ticket.active_run_id, ticket.solution_json = run.id, {}
    patch = body.facts_patch.model_dump(mode="json", exclude_unset=True)
    state = apply_facts(db, ticket, run, state, patch, actor, body.action_id, allow_replace=True)
    state = {"request": state["request"], "data_source": "mock", "evidence_refs": [], **execution,
             "ticket_metadata": {"priority": ticket.priority, "assignee_id": str(ticket.assignee_id) if ticket.assignee_id else None}}
    save_snapshot(db, ticket, run, state)
    db.add(ExecutionTask(run_id=run.id, kind="start", action_id=body.action_id))
    append_event(db, ticket, "run.reinvestigation_queued", {"reason": body.reason, "previous_run_id": str(old.id)})
    return finish_action(db, record, ticket, actor, body, "tickets.reinvestigate")


def contacted(db: Session, actor, ticket_id: UUID, body):
    if body.outcome != "contacted":
        raise AppError(422, "USE_RESULT_ACTION", "确认解决请显式结案；未解决请使用重新调查")
    record, replay = begin_action(db, actor, f"tickets.feedback:{ticket_id}", body)
    if replay:
        result = record.response_ref
        db.commit()
        return result
    ticket = lock_ticket(db, ticket_id, body.expected_version)
    if ticket.status != TicketStatus.PENDING_CONFIRMATION or not ticket.solution_json.get("reviewed"):
        raise AppError(409, "REVIEW_REQUIRED", "请先审核方案，再记录已联系客户")
    run = db.get(Run, ticket.active_run_id)
    ticket.solution_json = check_draft(db, ticket, run, latest_snapshot(db, run.id), ticket.solution_json)
    transition(ticket, TicketStatus.WAITING_CUSTOMER)
    ticket.result_json = {"contacted": True, "note": body.reason, "source": "human", "data_source": "mock"}
    append_event(db, ticket, "customer.contacted", {"note": body.reason, "source": "human"})
    return finish_action(db, record, ticket, actor, body, "tickets.feedback")
