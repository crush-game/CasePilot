"""只读取 runtime 样例的企业数据适配器，不接触评测标签。"""

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.providers.client import DomainDraft, ModelClient, ModelRequest
from app.tools.contracts import (
    AnalysisData, DownloadData, ErrorCode, FeedbackData, FeedbackRecord, KnowledgeData,
    KnowledgeRecord, LogLine, WindowData,
)
from app.tools.redaction import redact


RUNTIME_ROOT = Path(__file__).resolve().parents[3] / "fixtures" / "runtime"
SCENARIO_IDS = tuple(f"S{number:02d}" for number in range(1, 13))


def load_runtime(scenario_id: str) -> dict:
    if scenario_id not in SCENARIO_IDS:
        raise ValueError("未知的公开模拟场景")
    return json.loads((RUNTIME_ROOT / f"{scenario_id}.json").read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ToolContext:
    customer_ref: str
    customer_email: str  # 由系统绑定，不是工具参数，也不写进来源或模型输入。
    device_ref: str | None = None


class ToolIssue(Exception):
    def __init__(self, code: ErrorCode, *, status="error", data=None, refs=None):
        self.code, self.status, self.data, self.refs = code, status, data, refs or []


class MockAdapter:
    def __init__(self, context: ToolContext, runtime: dict, client: ModelClient | None = None):
        self.context, self.runtime = context, deepcopy(runtime)
        self.client = client or ModelClient()
        self.downloaded: set[str] = set()
        self.windows: dict[str, WindowData] = {}

    def owned_feedback(self, record_ref):
        record = next((row for row in self.runtime.get("feedbacks", []) if row["record_id"] == record_ref), None)
        if (not record or record["customer_ref"] != self.context.customer_ref
                or record["customer_email"] != self.context.customer_email
                or self.context.device_ref and record["device_ref"] != self.context.device_ref):
            raise ToolIssue(ErrorCode.FORBIDDEN)
        return record

    def dispatch(self, name, args):
        failure = self.runtime.get("tool_errors", {}).get(name)
        if failure:
            code = ErrorCode(failure)
            if code == ErrorCode.TIMEOUT:
                raise TimeoutError()
            raise ToolIssue(code)
        return getattr(self, name)(args)

    def search_knowledge(self, args):
        if not args.product_ref:
            return KnowledgeData(missing_fields=["product_ref"]), [], "needs_human"
        rows = [row for row in self.runtime.get("knowledge", []) if row["product_ref"] == args.product_ref]
        if args.firmware_version:
            rows = [row for row in rows if row["firmware_version"] == args.firmware_version]
        # P04 仅样例的确定性词项匹配；文档入库和 BM25 在 P05 实现。
        terms = args.query.casefold().split()
        rows = [row for row in rows if any(term in row["text"].casefold() for term in terms)]
        if not rows:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data")
        docs = [KnowledgeRecord(**{**row, "text": redact(row["text"])}) for row in rows]
        versions = {row.firmware_version for row in docs}
        conflicts = []
        for key in {(row.firmware_version, row.policy_key) for row in docs}:
            group = [row for row in docs if (row.firmware_version, row.policy_key) == key]
            if len({row.text for row in group}) > 1:
                conflicts.append([row.record_id for row in group])
        data = KnowledgeData(documents=docs, conflicts=conflicts,
                             missing_fields=["firmware_version"] if len(versions) > 1 else [])
        return data, [row.record_id for row in docs], "needs_human" if conflicts or data.missing_fields else "success"

    def get_feedbacks(self, args):
        if self.context.device_ref and args.device_ref != self.context.device_ref:
            raise ToolIssue(ErrorCode.FORBIDDEN)
        rows = [row for row in self.runtime.get("feedbacks", [])
                if row["customer_ref"] == self.context.customer_ref and row["customer_email"] == self.context.customer_email]
        if not rows:
            raise ToolIssue(ErrorCode.NO_FEEDBACK, status="no_data")
        # 先设备/平台，再故障时间；排序只用于稳定展示，绝不自动选最新。
        if args.device_ref:
            rows = [row for row in rows if row["device_ref"] == args.device_ref]
        if args.platform:
            rows = [row for row in rows if row["platform"] == args.platform]
        if args.occurred_at:
            rows = [row for row in rows if abs((datetime.fromisoformat(row["occurred_at"]) - args.occurred_at).total_seconds())
                    <= args.window_minutes * 60]
        if not rows:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data")
        missing = [name for name in ("device_ref", "occurred_at") if getattr(args, name) is None]
        records = [FeedbackRecord(record_id=row["record_id"], device_ref=row["device_ref"], platform=row["platform"],
                                  occurred_at=row["occurred_at"], attachment_available=bool(row.get("log_ref")),
                                  summary=redact(row["summary"])) for row in rows]
        data = FeedbackData(records=records, requires_selection=len(records) > 1 or bool(missing), missing_fields=missing)
        return data, [row.record_id for row in records], "needs_human" if data.requires_selection else "success"

    def download_log(self, args):
        feedback = self.owned_feedback(args.feedback_ref)
        if not feedback.get("log_ref"):
            raise ToolIssue(ErrorCode.NO_ATTACHMENT, status="no_data")
        log_ref = feedback["log_ref"]
        log = self.runtime.get("logs", {}).get(log_ref)
        if log is None:
            raise ToolIssue(ErrorCode.DOWNLOAD_FAILED)
        # 返回不含原始内容或磁盘路径的句柄，日志不直接进入模型。
        raw = json.dumps(log, ensure_ascii=False, sort_keys=True).encode()
        self.downloaded.add(log_ref)
        return DownloadData(log_ref=log_ref, checksum=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw)), [log_ref], "success"

    def extract_log_window(self, args):
        if args.log_ref not in self.downloaded:
            raise ToolIssue(ErrorCode.FORBIDDEN)
        log = self.runtime["logs"][args.log_ref]
        if not isinstance(log, list):
            raise ToolIssue(ErrorCode.PARSE_FAILED)
        try:
            snippets = [LogLine(**{**row, "text": redact(row["text"])}) for row in log
                        if args.start <= datetime.fromisoformat(row["occurred_at"]) <= args.end]
        except (ValueError, TypeError, KeyError):
            raise ToolIssue(ErrorCode.PARSE_FAILED) from None
        window_ref = f"window:{uuid4().hex}"
        data = WindowData(window_ref=window_ref, snippets=snippets,
                          viewed_range={"start": args.start, "end": args.end},
                          missing_fields=[] if snippets else ["matching_log_window"])
        self.windows[window_ref] = data
        refs = [row.record_id for row in snippets]
        if not snippets:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data", data=data)
        return data, refs, "success"

    def selected_window(self, args):
        window = self.windows.get(args.window_ref)
        if window is None:
            raise ToolIssue(ErrorCode.FORBIDDEN)
        return window

    def diagnose_wifi(self, args):
        window = self.selected_window(args)
        rows = [row for row in window.snippets if row.domain == "wifi"]
        if not rows:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data",
                            data=AnalysisData(analysis_mode="rule", domain="wifi", findings=[],
                                              limitations=["所查看窗口无 WiFi 记录，不能推断其他时段未发生故障。 "]))
        # 规则只报告可见事件，不推断硬件/网络根因。
        findings = [f"可见断连事件：{row.record_id}" for row in rows if "disconnect" in row.text.casefold()]
        return AnalysisData(analysis_mode="rule", domain="wifi", findings=findings,
                            limitations=["仅覆盖已查看时间窗；事件不等于根因。"]), [row.record_id for row in rows], "success"

    def analyze_domain(self, args):
        if args.domain not in {"wifi", "ota"}:
            raise ToolIssue(ErrorCode.UNSUPPORTED_DOMAIN)
        window = self.selected_window(args)
        rows = [row for row in window.snippets if row.domain == args.domain]
        if not rows:
            raise ToolIssue(ErrorCode.NO_MATCHING_RECORD, status="no_data",
                            data=AnalysisData(analysis_mode="model", domain=args.domain, findings=[],
                                              limitations=["缺少该领域日志，不使用其他领域事件代替根因证据。 "]))
        refs = [row.record_id for row in rows]
        result, usage = self.client.complete(ModelRequest(role="domain", input={"domain": args.domain,
            "snippets": [row.model_dump(mode="json") for row in rows]}, allowed_evidence_refs=refs), DomainDraft)
        return AnalysisData(analysis_mode="model", domain=args.domain, findings=result.findings,
                            limitations=result.limitations, model_usage=usage.model_dump()), result.evidence_refs, "success"


def default_runtime(context: ToolContext, occurred_at: str, *, fail=False) -> dict:
    """常规工作台的两条固定 Mock 资料；身份来自执行器锁定的工单。"""
    return {"knowledge": [{"record_id": "mock:mock_knowledge:v1", "product_ref": "DEMO", "firmware_version": "1.0",
                           "policy_key": "connection", "text": "【模拟资料】连接测试请核对设备与故障时间。"}],
            "feedbacks": [{"record_id": "mock:mock_fault:v1", "customer_ref": context.customer_ref,
                           "customer_email": context.customer_email, "device_ref": context.device_ref,
                           "platform": "android", "occurred_at": occurred_at, "summary": "【模拟反馈】连接测试事件。", "log_ref": None}],
            "tool_errors": {"search_knowledge": "TIMEOUT", "get_feedbacks": "TIMEOUT"} if fail else {}}
