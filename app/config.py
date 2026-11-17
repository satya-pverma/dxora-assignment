from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Dxora Assignment"
    openai_api_key: SecretStr = SecretStr("")
    llm_model: str = Field(default="gpt-6-luna", min_length=1)
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_max_output_tokens: int = Field(default=6000, ge=1000, le=16000)


@lru_cache
def get_settings() -> Settings:
    return Settings()
