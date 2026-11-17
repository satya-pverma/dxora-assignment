import re
from datetime import datetime, timezone
from urllib.parse import urlencode

from app.config import Settings
from app.platforms.base import PlatformAdapter, PlatformError, PublishedPost
from app.platforms.http import PlatformHTTP, require_text
from app.utils.message_validator import extract_cta_link


def link_facet(message: str) -> dict:
    link = extract_cta_link(message)
    return {
        "index": {
            "byteStart": len(message[: link.start].encode("utf-8")),
            "byteEnd": len(message[: link.end].encode("utf-8")),
        },
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link.url}],
    }


class BlueskyAdapter(PlatformAdapter):
    name = "bluesky"

    def __init__(self, settings: Settings, http: PlatformHTTP | None = None) -> None:
        self.settings = settings
        self.http = http or PlatformHTTP(settings.posting_timeout_seconds)
        self._uri: str | None = None

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        password = self.settings.bluesky_app_password.get_secret_value()
        if (
            not self.settings.bluesky_pds_url
            or not self.settings.bluesky_handle
            or not password.strip()
        ):
            raise PlatformError("missing_credentials")
        # Use only the configured origin; never follow a response-provided token destination.
        session = await self.http.request(
            "POST",
            f"{self.settings.bluesky_pds_url}/xrpc/com.atproto.server.createSession",
            payload={"identifier": self.settings.bluesky_handle, "password": password},
        )
        did = require_text(session, "did")
        token = require_text(session, "accessJwt")
        if not re.fullmatch(r"did:(?:plc|web):[A-Za-z0-9._:%-]+", did):
            raise PlatformError("invalid_response")
        published_at = datetime.now(timezone.utc)
        result = await self.http.request(
            "POST",
            f"{self.settings.bluesky_pds_url}/xrpc/com.atproto.repo.createRecord",
            token=token,
            payload={
                "repo": did,
                "collection": "app.bsky.feed.post",
                "validate": True,
                "record": {
                    "$type": "app.bsky.feed.post",
                    "text": message,
                    "createdAt": published_at.isoformat(),
                    "facets": [link_facet(message)],
                },
            },
            publishing=True,
        )
        try:
            uri = require_text(result, "uri")
            require_text(result, "cid")
            prefix = f"at://{did}/app.bsky.feed.post/"
            if not uri.startswith(prefix) or not re.fullmatch(
                r"[A-Za-z0-9._~:-]+", uri[len(prefix) :]
            ):
                raise PlatformError("invalid_response")
            self._uri = uri
            return PublishedPost(
                url=f"https://bsky.app/profile/{did}/post/{uri[len(prefix) :]}",
                public_access=False,
                published_at=published_at,
            )
        except (ValueError, PlatformError) as exc:
            raise PlatformError("outcome_uncertain") from exc

    async def verify_public(self, post: PublishedPost, message: str, cta_url: str) -> bool:
        query = urlencode({"uris": self._uri})
        result = await self.http.request(
            "GET",
            f"https://public.api.bsky.app/xrpc/app.bsky.feed.getPosts?{query}",
        )
        posts = result.get("posts")
        return (
            isinstance(posts, list)
            and len(posts) == 1
            and isinstance(posts[0], dict)
            and posts[0].get("uri") == self._uri
            and isinstance(posts[0].get("record"), dict)
            and posts[0]["record"].get("text") == message
        )
