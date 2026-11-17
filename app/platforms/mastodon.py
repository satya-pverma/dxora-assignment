from urllib.parse import quote

from pydantic import ValidationError

from app.config import Settings
from app.platforms.base import PlatformAdapter, PlatformError, PublishedPost
from app.platforms.http import PlatformHTTP, contains_message, publication_time, require_text


class MastodonAdapter(PlatformAdapter):
    name = "mastodon"

    def __init__(self, settings: Settings, http: PlatformHTTP | None = None) -> None:
        self.settings = settings
        self.http = http or PlatformHTTP(settings.posting_timeout_seconds)
        self._post_id: str | None = None

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        token = self.settings.mastodon_access_token.get_secret_value()
        if not self.settings.mastodon_base_url or not token.strip():
            raise PlatformError("missing_credentials")
        data = await self.http.request(
            "POST",
            f"{self.settings.mastodon_base_url}/api/v1/statuses",
            token=token,
            payload={"status": message, "visibility": "public"},
            publishing=True,
        )
        try:
            self._post_id = require_text(data, "id")
            if data.get("visibility") != "public":
                raise PlatformError("invalid_response")
            return PublishedPost(
                url=require_text(data, "url"),
                public_access=False,
                published_at=publication_time(data.get("created_at")),
            )
        except (PlatformError, ValidationError) as exc:
            raise PlatformError("outcome_uncertain") from exc

    async def verify_public(self, post: PublishedPost, message: str, cta_url: str) -> bool:
        data = await self.http.request(
            "GET",
            f"{self.settings.mastodon_base_url}/api/v1/statuses/{quote(self._post_id, safe='')}",
        )
        return (
            data.get("id") == self._post_id
            and data.get("visibility") == "public"
            and data.get("url") == str(post.url)
            and contains_message(data.get("content"), message)
        )
