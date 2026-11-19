from dataclasses import dataclass
from datetime import datetime, timezone

from pydantic import ValidationError

from app.providers.client import ModelFailure
from app.tools.contracts import (
    AnalysisData, BoundArgs, Contract, DomainArgs, DownloadArgs, DownloadData, ErrorCode,
    FeedbackArgs, FeedbackData, KnowledgeArgs, KnowledgeData, Source, ToolResult,
    WifiArgs, WindowArgs, WindowData,
)
from app.tools.mock import MockAdapter, ToolIssue
from app.tools.redaction import redact


@dataclass(frozen=True)
class ToolSpec:
    input_schema: type[BoundArgs]
    output_schema: type[Contract]


# 注册表只由代码维护；提示词和模型响应均不能新增工具或改变 schema。
TOOLS = {
    "search_knowledge": ToolSpec(KnowledgeArgs, KnowledgeData),
    "get_feedbacks": ToolSpec(FeedbackArgs, FeedbackData),
    "download_log": ToolSpec(DownloadArgs, DownloadData),
    "extract_log_window": ToolSpec(WindowArgs, WindowData),
    "diagnose_wifi": ToolSpec(WifiArgs, AnalysisData),
    "analyze_domain": ToolSpec(DomainArgs, AnalysisData),
}


def tool_schemas() -> dict:
    return {name: {"input": spec.input_schema.model_json_schema(),
                   "output": ToolResult[spec.output_schema].model_json_schema()} for name, spec in TOOLS.items()}


class ToolRegistry:
    def __init__(self, adapter: MockAdapter):
        self.adapter = adapter

    def call(self, name: str, arguments: dict) -> ToolResult:
        spec = TOOLS.get(name)
        status, data, refs, code = "error", None, [], None
        query = {}  # 拒绝的原始参数可能含其他客户邮箱/敏感内容，不回显或落证据。
        try:
            if spec is None:
                raise ToolIssue(ErrorCode.TOOL_NOT_ALLOWED)
            try:
                args = spec.input_schema.model_validate(arguments)
            except ValidationError:
                raise ToolIssue(ErrorCode.INVALID_ARGUMENTS) from None
            if args.customer_ref != self.adapter.context.customer_ref:
                raise ToolIssue(ErrorCode.FORBIDDEN)
            query = {key: redact(value) if isinstance(value, str) else value
                     for key, value in args.model_dump(mode="json").items()}
            data, refs, status = self.adapter.dispatch(name, args)
            data = spec.output_schema.model_validate(data.model_dump() if isinstance(data, Contract) else data)
        except ValidationError:
            code = ErrorCode.PARSE_FAILED
            data, refs, status, query = None, [], "error", {}
        except ToolIssue as exc:
            status, data, refs, code = exc.status, exc.data, exc.refs, exc.code
        except TimeoutError:
            code = ErrorCode.TIMEOUT
        except ModelFailure as exc:
            code = ErrorCode.TIMEOUT if exc.code == "MODEL_TIMEOUT" else ErrorCode.TOOL_FAILED
        except Exception:
            code = ErrorCode.TOOL_FAILED
        schema = ToolResult[spec.output_schema] if spec else ToolResult[Contract]
        return schema(status=status, data_source="mock", data_refs=refs, data=data,
                      error_code=code, retryable=code in {ErrorCode.TIMEOUT, ErrorCode.RATE_LIMITED},
                      source=Source(data_source="mock", adapter=getattr(self.adapter, "adapter_name", "mock-fixtures-v1"), record_ids=refs, query=query),
                      fetched_at=datetime.now(timezone.utc))
