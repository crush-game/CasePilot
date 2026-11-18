"""独立 Worker 与只读检查点对账入口。"""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import time
from uuid import UUID, uuid4

from dotenv import load_dotenv
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.types import Command
import psycopg
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.agents.graphs.mock import GRAPH_VERSION, build_graph
from app.config import get_settings
from app.domain.enums import TicketStatus
from app.repositories.database import get_engine
from app.repositories.models import ExecutionTask, Run, Ticket
from app.services.workflow_common import append_event, latest_snapshot, save_snapshot, transition
from app.workers.checkpoints import checkpoint_connection, setup_checkpoints, try_run_lock
from app.workers.context import ExecutionContext, Heartbeat, LeaseLost
from app.workers.faults import failpoint
from app.workers.projection import current_interrupt, project_nodes, project_result


def eligible_tasks(run_id=None, reconcile=False):
    expired = and_(ExecutionTask.status == "running", ExecutionTask.lease_until <= func.clock_timestamp())
    ready = and_(ExecutionTask.status == "queued", ExecutionTask.available_at <= func.clock_timestamp())
    with Session(get_engine()) as db:
        query = select(ExecutionTask.id, ExecutionTask.run_id, Run.ticket_id).join(Run, Run.id == ExecutionTask.run_id).join(
            Ticket, Ticket.id == Run.ticket_id,
        ).where(Ticket.active_run_id == Run.id, Run.status.in_(["queued", "running"]), expired if reconcile else or_(expired, ready))
        if run_id:
            query = query.where(Run.id == run_id)
        return list(db.execute(query.order_by(ExecutionTask.available_at, ExecutionTask.id).limit(50)))


def claim_task(connection, candidate):
    task_id, run_id, ticket_id = candidate
    with Session(get_engine(), expire_on_commit=False) as db:
        ticket = db.scalar(select(Ticket).where(Ticket.id == ticket_id).with_for_update(skip_locked=True))
        if ticket is None:
            return None
        run = db.scalar(select(Run).where(Run.id == run_id).with_for_update())
        task = db.scalar(select(ExecutionTask).where(ExecutionTask.id == task_id).with_for_update(skip_locked=True))
        now = db.scalar(select(func.clock_timestamp()))
        if task is None or ticket.active_run_id != run_id or ticket.status not in {TicketStatus.QUEUED, TicketStatus.RUNNING}:
            return None
        if task.status == "running" and (task.lease_until is None or task.lease_until > now):
            return None
        if task.status not in {"queued", "running"}:
            return None
        if task.status == "queued" and task.available_at > now:
            return None
        state = latest_snapshot(db, run_id)
        if ticket.status == TicketStatus.QUEUED:
            transition(ticket, TicketStatus.RUNNING)
            save_snapshot(db, ticket, run, state)
            append_event(db, ticket, "run.started", {"task_id": str(task.id), "data_source": "mock"})
        epoch = task.payload_json.get("budget_epoch", state.get("budget_epoch", 0))
        budget = run.budget_json or {}
        if budget.get("budget_epoch") != epoch or not budget.get("epoch_started_at"):
            history = budget.get("history", [])
            if budget:
                history = [*history, {key: value for key, value in budget.items() if key != "history"}]
            budget = {"budget_epoch": epoch, "epoch_started_at": now.isoformat(), "history": history}
        run.budget_json, run.status = budget, "running"
        task.status, task.lease_token = "running", uuid4()
        task.lease_until = now + timedelta(seconds=get_settings().worker_lease_seconds)
        task.attempt += 1
        db.commit()
        ctx = ExecutionContext(task.id, run.id, ticket.id, task.lease_token, ticket.version,
                               connection, get_engine(), epoch, datetime.fromisoformat(budget["epoch_started_at"]))
        return ctx, {**state, "case_version": ticket.version}, task.payload_json, task.kind, run.graph_version


def requeue(ctx):
    with Session(ctx.engine) as db:
        ticket, _, task = ctx.fenced(db)
        task.status, task.lease_token, task.lease_until = "queued", None, None
        append_event(db, ticket, "run.requeued", {"task_id": str(task.id)})
        db.commit()


def resume_already_consumed(snapshot, payload):
    return payload.get("action_id") in snapshot.values.get("consumed_action_ids", [])


def execute_claim(ctx, initial_state, payload, kind, graph_version, reconcile):
    saver = PostgresSaver(ctx.connection)
    graph = build_graph(saver, ctx)
    config = {"configurable": {"thread_id": str(ctx.run_id)}, "recursion_limit": 100}
    snapshot = graph.get_state(config)
    if graph_version != GRAPH_VERSION:
        project_result(ctx, snapshot, "GRAPH_VERSION_UNSUPPORTED")
        return
    if reconcile:
        # 对账只读检查点并补业务投影，绝不在这里重跑整张图或提交 resume。
        if ctx.control(snapshot.values or {}) == "TAKEOVER_REQUESTED":
            requeue(ctx)
            return
        pending_resume = kind == "resume" and not resume_already_consumed(snapshot, payload)
        if pending_resume:
            requeue(ctx)
        else:
            project_nodes(ctx, snapshot)
            if not project_result(ctx, snapshot):
                requeue(ctx)
        return
    failpoint("after_claim")
    forced_pause = ctx.control(snapshot.values or {}) == "TAKEOVER_REQUESTED" and bool(snapshot.values)
    if forced_pause:
        graph.update_state(config, {"stop_reason": "TAKEOVER_REQUESTED", "next_action": "human_interrupt", "complete": False,
                                    "budget_epoch": ctx.epoch, "case_version": ctx.case_version}, as_node="supervisor")
        snapshot = graph.get_state(config)
    paused = current_interrupt(snapshot)
    consumed = resume_already_consumed(snapshot, payload)
    if forced_pause:
        value = None
    elif kind == "resume" and not consumed and not paused:
        project_result(ctx, snapshot, "CHECKPOINT_MISSING")
        return
    elif kind == "resume" and paused and not consumed:
        if paused.id != payload.get("pause_key"):
            project_result(ctx, snapshot, "PAUSE_MISMATCH")
            return
        value = Command(resume={**payload, "case_version": ctx.case_version}, update={"case_version": ctx.case_version})
    elif paused or (snapshot.values.get("complete") and not snapshot.next):
        project_nodes(ctx, snapshot)
        project_result(ctx, snapshot)
        return
    elif snapshot.values:
        value = None
    else:
        value = {**initial_state, "completed_steps": [], "consumed_action_ids": [], "budget_epoch": ctx.epoch}
    try:
        for _ in graph.stream(value, config, stream_mode="values", durability="sync"):
            snapshot = graph.get_state(config)
            if kind == "resume" and resume_already_consumed(snapshot, payload):
                failpoint("after_resume_checkpoint")
            project_nodes(ctx, snapshot)
        snapshot = graph.get_state(config)
        if current_interrupt(snapshot):
            failpoint("after_interrupt_checkpoint")
        elif snapshot.values.get("complete") and not snapshot.next:
            failpoint("after_finish_checkpoint")
        project_nodes(ctx, snapshot)
        project_result(ctx, snapshot)
    except (LeaseLost, psycopg.Error, SQLAlchemyError):
        raise
    except Exception:
        # 框架异常转为持久人工暂停；数据库/执行权失败走上面的恢复路径。
        ctx.control({}, allow_pause=True)
        graph.update_state(config, {"stop_reason": "FRAMEWORK_ERROR", "next_action": "human_interrupt", "complete": False,
                                    "budget_epoch": ctx.epoch, "case_version": ctx.case_version}, as_node="supervisor")
        graph.invoke(None, config, durability="sync")
        project_result(ctx, graph.get_state(config))


def run_once(run_id=None, reconcile=False):
    for candidate in eligible_tasks(run_id, reconcile):
        with checkpoint_connection() as connection:
            if not try_run_lock(connection, candidate.run_id):
                continue
            claimed = claim_task(connection, candidate)
            if claimed is None:
                continue
            ctx, state, payload, kind, version = claimed
            try:
                with Heartbeat(ctx):
                    execute_claim(ctx, state, payload, kind, version, reconcile)
            except (LeaseLost, psycopg.Error, SQLAlchemyError):
                # 不重连旧执行；保留任务供租约到期后对账。
                return True
            return True
    return False


def main():
    load_dotenv(Path(__file__).resolve().parents[3] / ".env", encoding="utf-8-sig")
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["setup", "worker", "reconcile"])
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--run-id", type=UUID)
    args = parser.parse_args()
    if args.mode == "setup":
        setup_checkpoints()
        print("检查点表已串行初始化。")
        return
    try:
        while True:
            try:
                processed = run_once(args.run_id, reconcile=args.mode == "reconcile")
            except (psycopg.Error, SQLAlchemyError):
                if args.once:
                    raise SystemExit("存储暂不可用，本次未完成任务处理。") from None
                print("存储暂不可用，等待下次检查。", flush=True)
                time.sleep(get_settings().worker_poll_seconds)
                continue
            if args.once:
                print(json.dumps({"processed": processed, "mode": args.mode}))
                return
            if not processed:
                time.sleep(get_settings().worker_poll_seconds)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
