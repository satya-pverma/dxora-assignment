from datetime import datetime, timezone

from bs4 import BeautifulSoup

from app.config import Settings
from app.platforms.base import PlatformAdapter, PlatformError, PublishedPost
from app.platforms.http import PlatformHTTP, contains_message


def verify_telegram_html(html: str, username: str, post_id: int, message: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    widget = soup.find(attrs={"data-post": f"{username}/{post_id}"})
    if not widget:
        return False
    content = widget.select_one(".tgme_widget_message_text")
    return content is not None and contains_message(str(content), message)


class TelegramAdapter(PlatformAdapter):
    name = "telegram"

    def __init__(self, settings: Settings, http: PlatformHTTP | None = None) -> None:
        self.settings = settings
        self.http = http or PlatformHTTP(settings.posting_timeout_seconds)
        self._post_id: int | None = None

    async def _call(self, method: str, payload: dict, *, publishing: bool = False) -> dict:
        token = self.settings.telegram_bot_token.get_secret_value()
        data = await self.http.request(
            "POST",
            f"https://api.telegram.org/botredacted/{method}",
            payload=payload,
            publishing=publishing,
            secret_path=f"/bot{token}/{method}",
        )
        if data.get("ok") is not True:
            code = data.get("error_code")
            code = code if type(code) is int else None
            known = {401: "authentication_failed", 403: "permission_denied", 429: "rate_limited"}
            raise PlatformError(
                known.get(code, "outcome_uncertain" if publishing else "provider_error")
            )
        result = data.get("result")
        if not isinstance(result, dict):
            raise PlatformError("outcome_uncertain" if publishing else "invalid_response")
        return result

    def _validate_chat(self, chat: dict) -> int:
        username = self.settings.telegram_channel_username
        chat_id = chat.get("id")
        if (
            type(chat_id) is not int
            or chat_id >= 0
            or chat.get("type") != "channel"
            or not isinstance(chat.get("username"), str)
            or chat["username"].lower() != username
            or (
                self.settings.telegram_channel_id
                and str(chat_id) != self.settings.telegram_channel_id
            )
        ):
            raise PlatformError("invalid_configuration")
        return chat_id

    async def publish(self, message: str, cta_url: str) -> PublishedPost:
        username = self.settings.telegram_channel_username
        if not username or not self.settings.telegram_bot_token.get_secret_value():
            raise PlatformError("missing_credentials")
        target = self.settings.telegram_channel_id or f"@{username}"
        chat = await self._call("getChat", {"chat_id": target})
        chat_id = self._validate_chat(chat)
        result = await self._call(
            "sendMessage",
            {"chat_id": chat_id, "text": message, "link_preview_options": {"is_disabled": True}},
            publishing=True,
        )
        try:
            returned_chat = result.get("chat")
            if not isinstance(returned_chat, dict) or self._validate_chat(returned_chat) != chat_id:
                raise ValueError
            self._post_id = result.get("message_id")
            timestamp = result.get("date")
            if (
                type(self._post_id) is not int
                or self._post_id <= 0
                or type(timestamp) is not int
                or result.get("text") != message
            ):
                raise ValueError
            published_at = datetime.fromtimestamp(timestamp, timezone.utc)
        except (ValueError, OverflowError, OSError, PlatformError) as exc:
            raise PlatformError("outcome_uncertain") from exc
        return PublishedPost(
            url=f"https://t.me/{username}/{self._post_id}",
            public_access=False,
            published_at=published_at,
        )

    async def verify_public(self, post: PublishedPost, message: str, cta_url: str) -> bool:
        html = await self.http.get_html(f"{post.url}?embed=1&mode=tme")
        return verify_telegram_html(
            html, self.settings.telegram_channel_username, self._post_id, message
        )
