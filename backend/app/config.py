from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AFTERSALES_", extra="ignore")

    database_url: SecretStr
    model_provider: Literal["mock"] = "mock"
    enterprise_data_provider: Literal["mock"] = "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
