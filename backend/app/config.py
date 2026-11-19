from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.providers.client import ModelProfile, Role


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AFTERSALES_", extra="ignore")

    database_url: SecretStr
    model_provider: Literal["mock"] = "mock"
    model_profiles: dict[Role, ModelProfile] = Field(default_factory=dict)
    enterprise_data_provider: Literal["mock"] = "mock"
    session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    cookie_secure: bool = False
    worker_lease_seconds: int = Field(default=30, ge=2, le=300)
    worker_poll_seconds: float = Field(default=1, ge=0.1, le=10)
    ingestion_lease_seconds: int = Field(default=60, ge=2, le=300)
    run_timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_budget_epochs: int = Field(default=5, ge=1, le=20)
    max_mock_steps: int = Field(default=24, ge=1, le=100)
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


@lru_cache
def get_settings() -> Settings:
    return Settings()
