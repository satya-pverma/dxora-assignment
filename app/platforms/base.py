"""Contracts shared by the independent publishing integrations."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, HttpUrl, StrictBool, field_validator

PublishingPlatform = Literal["mastodon", "bluesky", "wordpress", "tumblr", "telegram"]
PUBLISHING_PLATFORMS: tuple[PublishingPlatform, ...] = (
    "mastodon",
    "bluesky",
    "wordpress",
    "tumblr",
    "telegram",
)


class PlatformError(Exception):
    """Adapters use stable codes, never upstream bodies, for public errors."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class PublishedPost(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    url: HttpUrl
    public_access: StrictBool
    published_at: datetime

    @field_validator("published_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("Publication timestamps must include a timezone.")
        return value

    @field_validator("url")
    @classmethod
    def reject_url_credentials(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password:
            raise ValueError("Published URLs must not contain credentials.")
        return value


class PlatformAdapter(ABC):
    name: PublishingPlatform

    @abstractmethod
    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        """Publish once and return the provider's confirmed post details.

        Raise PlatformError with a safe code on failure. Do not retry uncertain
        publication outcomes blindly. Return public_access=False until verified;
        orchestration invokes verify_public separately after confirmation.
        """

    async def verify_public(self, post: PublishedPost, message: str, cta_url: str) -> bool:
        """Verify anonymously after confirmation; the default preserves the adapter result."""
        return post.public_access
