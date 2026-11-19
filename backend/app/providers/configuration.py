import hashlib
import json
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from app.tools.contracts import Contract


class ServiceProfile(Contract):
    model: str = Field(min_length=1, max_length=200)
    base_url: str
    timeout_seconds: float = Field(default=45.0, gt=0, le=120)
    max_input_tokens: int = Field(ge=1, le=200000)
    max_output_tokens: int = Field(default=0, ge=0, le=8192)
    input_price_per_million: float = Field(ge=0, allow_inf_nan=False)
    output_price_per_million: float = Field(default=0.0, ge=0, allow_inf_nan=False)
    currency: Literal["CNY", "USD"] = "CNY"
    price_version: str = Field(min_length=1, max_length=120)
    response_format: Literal["json_object", "json_schema"] = "json_object"
    enable_thinking: Literal[False] = False
    thinking_control: Literal["omit", "enable_thinking"] = "omit"

    @field_validator("base_url")
    @classmethod
    def explicit_endpoint(cls, value):
        parsed = urlsplit(value)
        if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.scheme not in {"http", "https"}
                or parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}):
            raise ValueError("只接受无内嵌凭据的 HTTPS 地址，本机契约测试可用 HTTP")
        return value.rstrip("/")


class EmbeddingConfig(ServiceProfile):
    dimensions: int = Field(ge=1, le=4096)
    preprocess_version: Literal["heading-text-v1"] = "heading-text-v1"

    def fingerprint(self, mode="real"):
        # 定价变更不改变向量语义；服务端点、模型、维度和预处理变更必须新建 profile。
        value = {key: getattr(self, key) for key in ("model", "base_url", "dimensions", "preprocess_version")}
        value["inference_mode"] = mode
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class ProviderConfig(Contract):
    config_version: str
    chat: ServiceProfile
    embedding: EmbeddingConfig
    rerank: ServiceProfile
    chat_roles: dict[Literal["parse", "supervisor", "solution", "domain"], ServiceProfile] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_output(self):
        if any(profile.max_output_tokens < 1 for profile in [self.chat, *self.chat_roles.values()]):
            raise ValueError("真实聊天模型必须显式设置输出上限")
        if self.embedding.max_output_tokens or self.rerank.max_output_tokens:
            raise ValueError("embedding/rerank 只计算输入额度")
        return self


def load_provider_config(path: Path | None = None) -> ProviderConfig:
    root = Path(__file__).resolve().parents[3]
    path = path or root / "config" / "providers.siliconflow.json"
    if not path.is_absolute():
        path = root / path
    return ProviderConfig.model_validate_json(path.read_text(encoding="utf-8"))
