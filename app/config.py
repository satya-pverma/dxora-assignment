from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.platforms.base import PUBLISHING_PLATFORMS, PublishingPlatform


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Dxora Assignment"
    openai_api_key: SecretStr = SecretStr("")
    llm_model: str = Field(default="gpt-6-luna", min_length=1)
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_max_output_tokens: int = Field(default=6000, ge=1000, le=16000)
    posting_platforms: list[PublishingPlatform] = Field(
        default_factory=lambda: list(PUBLISHING_PLATFORMS), min_length=1, max_length=5
    )
    posting_timeout_seconds: float = Field(default=15, gt=0, le=60)

    @field_validator("posting_platforms")
    @classmethod
    def require_unique_platforms(cls, value: list[PublishingPlatform]) -> list[PublishingPlatform]:
        if len(set(value)) != len(value):
            raise ValueError("Posting platforms must be unique.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
