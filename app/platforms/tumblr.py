import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from app.config import Settings
from app.platforms.base import PlatformAdapter, PlatformError, PublishedPost
from app.platforms.http import PlatformHTTP, contains_message
from app.services.tumblr_tokens import get_tumblr_token
from app.utils.message_validator import extract_cta_link

logger = logging.getLogger(__name__)


def npf_text(message: str) -> dict:
    link = extract_cta_link(message)
    return {
        "type": "text",
        "text": message,
        "formatting": [{"start": link.start, "end": link.end, "type": "link", "url": link.url}],
    }


def verify_tumblr_html(html: str, url: str, message: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.find("link", rel="canonical")
    if not canonical or not isinstance(canonical.get("href"), str):
        return False
    target = urlsplit(canonical["href"])
    expected = urlsplit(url)
    return (
        target.scheme == "https"
        and target.netloc == expected.netloc
        and (
            target.path.rstrip("/") == expected.path or target.path.startswith(expected.path + "/")
        )
        and contains_message(html, message)
    )


class TumblrAdapter(PlatformAdapter):
    name = "tumblr"

    def __init__(self, settings: Settings, http: PlatformHTTP | None = None) -> None:
        self.settings = settings
        self.http = http or PlatformHTTP(settings.posting_timeout_seconds)

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        try:
            token = await get_tumblr_token(self.settings)
            if not isinstance(token, str):
                raise TypeError
        except PlatformError:
            raise
        except Exception as exc:
            logger.error("Tumblr token acquisition failed exception_type=%s", type(exc).__name__)
            raise PlatformError("token_storage_unavailable") from None
        blog = self.settings.tumblr_blog_identifier
        if not blog or not token.strip():
            raise PlatformError("missing_credentials")
        data = await self.http.request(
            "POST",
            f"https://api.tumblr.com/v2/blog/{blog}/posts",
            token=token,
            payload={
                "content": [npf_text(message)],
                "state": "published",
                "send_to_twitter": False,
            },
            publishing=True,
        )
        if not isinstance(data, dict):
            raise PlatformError("outcome_uncertain")
        meta = data.get("meta")
        status = meta.get("status") if isinstance(meta, dict) else None
        if type(status) is int and status in {401, 403, 429}:
            raise PlatformError(
                {401: "authentication_failed", 403: "permission_denied", 429: "rate_limited"}[
                    status
                ]
            )
        result = data.get("response")
        post_id = result.get("id") if isinstance(result, dict) else None
        if (
            status != 201
            or not isinstance(post_id, str)
            or len(post_id) > 20
            or not post_id.isascii()
            or not post_id.isdecimal()
            or not 0 < int(post_id) < 2**64
        ):
            raise PlatformError("outcome_uncertain")
        return PublishedPost(
            url=f"https://{blog}/post/{post_id}",
            public_access=False,
            published_at=datetime.now(timezone.utc),
        )

    async def verify_public(self, post: PublishedPost, message: str, cta_url: str) -> bool:
        return verify_tumblr_html(await self.http.get_html(str(post.url)), str(post.url), message)
