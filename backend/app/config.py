from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AFTERSALES_", extra="ignore")

    database_url: SecretStr
    model_provider: Literal["mock"] = "mock"
    enterprise_data_provider: Literal["mock"] = "mock"
    session_ttl_seconds: int = Field(default=28800, ge=300, le=86400)
    cookie_secure: bool = False
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
