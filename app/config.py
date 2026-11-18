import re
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.platforms.base import PUBLISHING_PLATFORMS, PublishingPlatform
from app.utils.validators import normalize_website_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_name: str = "Dxora Assignment"
    demo_access_key: SecretStr = SecretStr("")
    openai_api_key: SecretStr = SecretStr("")
    llm_provider: Literal["openai", "gemini"] = "openai"
    llm_model: str = Field(default="gpt-6-luna", min_length=1)
    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = Field(
        default="gemini-3.8-flash", min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$"
    )
    llm_timeout_seconds: float = Field(default=30, gt=0, le=120)
    llm_max_output_tokens: int = Field(default=6000, ge=1000, le=16000)
    posting_platforms: list[PublishingPlatform] = Field(
        default_factory=lambda: list(PUBLISHING_PLATFORMS), min_length=1, max_length=5
    )
    posting_timeout_seconds: float = Field(default=15, gt=0, le=60)
    mastodon_base_url: str = ""
    mastodon_access_token: SecretStr = SecretStr("")
    bluesky_pds_url: str = "https://bsky.social"
    bluesky_handle: str = ""
    bluesky_app_password: SecretStr = SecretStr("")
    wordpress_site_id: str = Field(default="", pattern=r"^[a-zA-Z0-9.-]*$")
    wordpress_access_token: SecretStr = SecretStr("")
    tumblr_blog_identifier: str = ""
    tumblr_access_token: SecretStr = SecretStr("")
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_channel_id: str = ""
    telegram_channel_username: str = ""

    @field_validator("tumblr_blog_identifier")
    @classmethod
    def require_tumblr_blog(cls, value: str) -> str:
        if not value:
            return value
        value = value.lower()
        if not value.endswith(".tumblr.com"):
            value += ".tumblr.com"
        if not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,30}[a-z0-9])?\.tumblr\.com", value):
            raise ValueError("Use a Tumblr blog name or its name.tumblr.com hostname.")
        return value

    @field_validator("telegram_bot_token")
    @classmethod
    def require_bot_token_format(cls, value: SecretStr) -> SecretStr:
        token = value.get_secret_value()
        if token and not re.fullmatch(r"[0-9]+:[A-Za-z0-9_-]+", token):
            raise ValueError("Telegram bot token has an invalid format.")
        return value

    @field_validator("telegram_channel_username")
    @classmethod
    def require_channel_username(cls, value: str) -> str:
        if not value:
            return value
        value = value.removeprefix("@").lower()
        if not re.fullmatch(r"[a-z][a-z0-9_]{4,31}", value):
            raise ValueError("Use a public Telegram channel username without a URL.")
        return value

    @field_validator("telegram_channel_id")
    @classmethod
    def require_channel_id(cls, value: str) -> str:
        if value and not re.fullmatch(r"-100[0-9]+", value):
            raise ValueError("An optional Telegram channel ID must use the -100 numeric format.")
        return value

    @field_validator("mastodon_base_url", "bluesky_pds_url")
    @classmethod
    def require_https_origin(cls, value: str) -> str:
        if not value:
            return value
        url = normalize_website_url(value)
        if url.scheme != "https" or url.path not in {"", "/"} or url.query or url.fragment:
            raise ValueError("Platform base URLs must be HTTPS origins without paths or queries.")
        # Check the original fragment too; the general normalizer intentionally removes it.
        if "#" in value:
            raise ValueError("Platform base URLs must not contain fragments.")
        return str(url).rstrip("/")

    @field_validator("posting_platforms")
    @classmethod
    def require_unique_platforms(cls, value: list[PublishingPlatform]) -> list[PublishingPlatform]:
        if len(set(value)) != len(value):
            raise ValueError("Posting platforms must be unique.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
