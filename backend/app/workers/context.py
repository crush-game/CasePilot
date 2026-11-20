from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import threading
from uuid import UUID, uuid5

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.providers.client import ModelClient, ModelRequest, SolutionDraft
from app.repositories.models import ExecutionTask, Run, Ticket, ToolExecution
from app.services.tickets import digest
from app.tools.mock import MockAdapter, ToolContext, default_runtime
from app.tools.redaction import redact
from app.tools.registry import ToolRegistry
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
    checkpoint_io_lock: object = field(default_factory=threading.Lock)

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
        # Saver 后台写入会进入 pipeline；连接探针须共享其临界区，不能插入 pipeline。
        with self.checkpoint_io_lock:
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
        policy = state.get("agent_config", {}).get("policy", {})
        if not allow_pause and (
            self.elapsed() >= policy.get("timeout_seconds", get_settings().run_timeout_seconds)
            or sum(step["epoch"] == self.epoch for step in state.get("completed_steps", [])) >= (
                policy.get("max_steps", get_settings().max_agent_steps) if state.get("graph_version") in {"supervisor-v1", "supervisor-v2"} else get_settings().max_mock_steps)
        ):
            return "BUDGET_EXHAUSTED"
        return None

    def tool(self, name: str, state: dict, logical_step: str):
        action_id = uuid5(self.run_id, f"{self.epoch}:{logical_step}:{name}")
        args = {"device_ref": state["request"].get("device_ref"), "occurred_at": state["request"].get("occurred_at")}
        with Session(self.engine) as db:
            ticket, _, _ = self.fenced(db)
            existing = db.scalar(select(ToolExecution).where(
                ToolExecution.run_id == self.run_id, ToolExecution.logical_action_id == action_id,
            ))
            if existing is not None:
                if existing.args_hash != digest(args):
                    raise RuntimeError("逻辑工具动作参数不一致")
                return existing.result_refs
            # 兼容 mock-v1 的逻辑动作/缓存键；内部固定步骤映射到 P04 的受控工具。
            # 当前适配器只读本地 Mock，后续外部 I/O 不应放在这个业务短事务内。
            context = ToolContext(customer_ref=f"customer:{ticket.id.hex}", customer_email=ticket.customer_email,
                                  device_ref=ticket.device_ref)
            registry = ToolRegistry(MockAdapter(context, default_runtime(context, args["occurred_at"],
                fail="[MOCK_ERROR]" in state["request"]["feedback_text"])))
            if name == "mock_knowledge":
                tool_name = "search_knowledge"
                parameters = {"customer_ref": context.customer_ref, "query": "连接", "product_ref": "DEMO", "firmware_version": "1.0"}
            elif name == "mock_fault":
                tool_name = "get_feedbacks"
                parameters = {"customer_ref": context.customer_ref, **args}
            else:
                raise ValueError("固定图调用了未注册的内部工具")
            result = registry.call(tool_name, parameters).model_dump(mode="json")
            result["evidence_refs"] = result["data_refs"]
            db.execute(insert(ToolExecution).values(
                run_id=self.run_id, logical_action_id=action_id, tool_name=tool_name, args_hash=digest(args),
                status="succeeded" if result["status"] == "success" else "failed", result_refs=result, error_code=result["error_code"],
            ))
            db.commit()
        failpoint("after_tool_write")
        self.control(state)
        return result

    def model(self, state: dict):
        self.control(state, allow_pause=True)
        client = ModelClient(get_settings().model_profiles)
        output, usage = client.complete(ModelRequest(role="solution", input={
            "feedback_text": redact(state["request"]["feedback_text"]),
            "device_ref": state["request"].get("device_ref"), "occurred_at": state["request"].get("occurred_at"),
        }, allowed_evidence_refs=state.get("evidence_refs", [])), SolutionDraft)
        self.control(state, allow_pause=True)
        return output.model_dump(mode="json"), usage.model_dump()


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
