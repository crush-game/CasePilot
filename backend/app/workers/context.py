from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import threading
from uuid import UUID, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.models import ExecutionTask, Run, Ticket, ToolExecution
from app.services.tickets import digest
from app.workers.faults import failpoint


class LeaseLost(Exception):
    """执行权或检查点连接失效；旧执行必须停止，不透明重连。"""


@dataclass
class ExecutionContext:
    task_id: UUID
    run_id: UUID
    ticket_id: UUID
    lease_token: UUID
    case_version: int
    connection: object
    engine: object
    epoch: int
    epoch_started_at: datetime
    lost: threading.Event = field(default_factory=threading.Event)

    def elapsed(self):
        return max(0, (datetime.now(timezone.utc) - self.epoch_started_at).total_seconds())

    def _validate(self, task, ticket, run, now):
        if (self.lost.is_set() or task is None or ticket is None or run is None or task.status != "running"
                or task.lease_token != self.lease_token or task.lease_until is None
                or task.lease_until <= now or ticket.active_run_id != self.run_id
                or ticket.version != self.case_version or run.case_version != self.case_version):
            raise LeaseLost("执行权已失效")

    def fenced(self, db: Session):
        # 锁顺序统一为 ticket→run→task；同一独占连接仍须持有检查点锁。
        if self.connection.closed or self.lost.is_set():
            raise LeaseLost("检查点连接已关闭")
        self.connection.execute("SELECT 1")
        ticket = db.scalar(select(Ticket).where(Ticket.id == self.ticket_id).with_for_update())
        run = db.scalar(select(Run).where(Run.id == self.run_id).with_for_update())
        task = db.scalar(select(ExecutionTask).where(ExecutionTask.id == self.task_id).with_for_update())
        now = db.scalar(select(func.clock_timestamp()))
        self._validate(task, ticket, run, now)
        return ticket, run, task

    def control(self, state: dict, allow_pause=False):
        with Session(self.engine) as db:
            _, run, _ = self.fenced(db)
            if run.cancel_requested:
                return "TAKEOVER_REQUESTED" if not allow_pause else None
        if not allow_pause and (
            self.elapsed() >= get_settings().run_timeout_seconds
            or sum(step["epoch"] == self.epoch for step in state.get("completed_steps", [])) >= get_settings().max_mock_steps
        ):
            return "BUDGET_EXHAUSTED"
        return None

    def tool(self, name: str, state: dict, logical_step: str):
        action_id = uuid5(self.run_id, f"{self.epoch}:{logical_step}:{name}")
        args = {"device_ref": state["request"].get("device_ref"), "occurred_at": state["request"].get("occurred_at")}
        with Session(self.engine) as db:
            self.fenced(db)
            existing = db.scalar(select(ToolExecution).where(
                ToolExecution.run_id == self.run_id, ToolExecution.logical_action_id == action_id,
            ))
            if existing is not None:
                if existing.args_hash != digest(args):
                    raise RuntimeError("逻辑工具动作参数不一致")
                return existing.result_refs
            # P02 仅固定只读 Mock，不查询真实日志、不调用模型。
            error = "[MOCK_ERROR]" in state["request"]["feedback_text"]
            result = {"status": "error" if error else "success", "data_source": "mock",
                      "evidence_refs": [f"mock:{name}:v1"], "error_code": "MOCK_TIMEOUT" if error else None}
            db.execute(insert(ToolExecution).values(
                run_id=self.run_id, logical_action_id=action_id, tool_name=name, args_hash=digest(args),
                status="failed" if error else "succeeded", result_refs=result, error_code=result["error_code"],
            ))
            db.commit()
        failpoint("after_tool_write")
        self.control(state)
        return result


class Heartbeat:
    def __init__(self, context):
        self.context = context
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        ctx = self.context
        while not self.stop.wait(get_settings().worker_lease_seconds / 3):
            try:
                with Session(ctx.engine) as db:
                    result = db.execute(update(ExecutionTask).where(
                        ExecutionTask.id == ctx.task_id, ExecutionTask.status == "running",
                        ExecutionTask.lease_token == ctx.lease_token,
                        ExecutionTask.lease_until > func.clock_timestamp(),
                    ).values(lease_until=func.clock_timestamp() + timedelta(seconds=get_settings().worker_lease_seconds)))
                    db.commit()
                    if result.rowcount != 1:
                        ctx.lost.set()
                        return
            except Exception:
                ctx.lost.set()
                return

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop.set()
        self.thread.join(timeout=4)
