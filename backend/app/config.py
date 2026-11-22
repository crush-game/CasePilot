from functools import lru_cache
from pathlib import Path
import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.providers.client import ModelProfile, Role
from app.services.calendar import ServiceCalendar


class SupportDemoDevice(BaseModel):
    customer_email: str = Field(max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.test$")
    device_ref: str = Field(min_length=1, max_length=128)
    product_ref: str = Field(min_length=1, max_length=120)
    firmware_version: str = Field(min_length=1, max_length=120)
    platform: Literal["android", "ios"]
    app_version: str = Field(min_length=1, max_length=120)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AFTERSALES_", extra="ignore")

    database_url: SecretStr
    model_provider: Literal["mock"] = "mock"
    workflow_graph_version: Literal["mock-v1", "supervisor-v1", "supervisor-v2"] = "mock-v1"
    enterprise_mock_fixture: str = Field(default="p08-demo", pattern=r"^[a-z0-9_-]{1,80}$")
    support_demo_devices: dict[UUID, list[SupportDemoDevice]] = Field(default_factory=dict)
    weekly_report_enabled: bool = False
    weekly_report_group: str = Field(default="after-sales", pattern=r"^[a-zA-Z0-9_-]{1,64}$")
    weekly_report_webhook: SecretStr | None = None
    weekly_report_origin: str = "http://127.0.0.1:5173"
    model_profiles: dict[Role, ModelProfile] = Field(default_factory=dict)
    provider_api_key: SecretStr | None = None
    provider_config_path: Path | None = None
    provider_budget_id: UUID | None = None
    enterprise_data_provider: Literal["mock"] = "mock"
    session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    cookie_secure: bool = False
    service_calendar: ServiceCalendar | None = None
    worker_lease_seconds: int = Field(default=30, ge=2, le=300)
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=10)
    ingestion_lease_seconds: int = Field(default=60, ge=2, le=300)
    run_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_budget_epochs: int = Field(default=5, ge=1, le=20)
    max_mock_steps: int = Field(default=24, ge=1, le=100)
    max_agent_steps: int = Field(default=64, ge=8, le=150)
    allowed_origins: list[str] = [
        "http://127.0.0.1:5173", "http://localhost:5173",
        "http://127.0.0.1:8000", "http://localhost:8000",
    ]

    @field_validator("allowed_origins")
    @classmethod
    def explicit_origins(cls, values):
        if any("*" in value or not value.startswith(("http://", "https://")) for value in values):
            raise ValueError("只允许显式配置 HTTP/HTTPS 来源")
        return values

    @field_validator("weekly_report_webhook")
    @classmethod
    def feishu_webhook(cls, value):
        if value and not re.fullmatch(r"https://open\.feishu\.cn/open-apis/bot/v2/hook/[A-Za-z0-9_-]{16,100}",
                                      value.get_secret_value()):
            raise ValueError("周报 Webhook 必须是飞书群机器人地址")
        return value

    @field_validator("weekly_report_origin")
    @classmethod
    def report_origin(cls, value):
        if not re.fullmatch(r"https?://[a-zA-Z0-9.-]+(?::[0-9]+)?/?", value):
            raise ValueError("周报面板地址须为明确的 HTTP/HTTPS 站点")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
