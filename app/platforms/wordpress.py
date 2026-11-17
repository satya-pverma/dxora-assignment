from html import escape

from pydantic import ValidationError

from app.config import Settings
from app.platforms.base import PlatformAdapter, PlatformError, PublishedPost
from app.platforms.http import PlatformHTTP, contains_message, publication_time, require_text
from app.utils.message_validator import extract_cta_link


def message_html(message: str) -> str:
    link = extract_cta_link(message)
    return (
        escape(message[: link.start])
        + f'<a href="{escape(link.url, quote=True)}">{escape(message[link.start : link.end])}</a>'
        + escape(message[link.end :])
    ).replace("\n", "<br>\n")


class WordPressAdapter(PlatformAdapter):
    name = "wordpress"

    def __init__(self, settings: Settings, http: PlatformHTTP | None = None) -> None:
        self.settings = settings
        self.http = http or PlatformHTTP(settings.posting_timeout_seconds)
        self._post_id: int | None = None

    @property
    def endpoint(self) -> str:
        return f"https://public-api.wordpress.com/rest/v1.1/sites/{self.settings.wordpress_site_id}/posts"

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        token = self.settings.wordpress_access_token.get_secret_value()
        if not self.settings.wordpress_site_id or not token.strip():
            raise PlatformError("missing_credentials")
        title = message[: extract_cta_link(message).start].strip()[:80] or "Business update"
        data = await self.http.request(
            "POST",
            f"{self.endpoint}/new/",
            token=token,
            payload={"title": title, "content": message_html(message), "status": "publish"},
            publishing=True,
        )
        try:
            self._post_id = data.get("ID")
            if (
                type(self._post_id) is not int
                or self._post_id <= 0
                or data.get("status") != "publish"
            ):
                raise PlatformError("invalid_response")
            return PublishedPost(
                url=require_text(data, "URL"),
                public_access=False,
                published_at=publication_time(data.get("date")),
            )
        except (PlatformError, ValidationError) as exc:
            raise PlatformError("outcome_uncertain") from exc

    async def verify_public(self, post: PublishedPost, message: str, cta_url: str) -> bool:
        data = await self.http.request("GET", f"{self.endpoint}/{self._post_id}/")
        return (
            data.get("ID") == self._post_id
            and data.get("status") == "publish"
            and data.get("URL") == str(post.url)
            and contains_message(data.get("content"), message)
        )
