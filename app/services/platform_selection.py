"""Expose credential presence, never credential values, to the dashboard."""

from pydantic import SecretStr

from app.config import Settings
from app.platforms.base import PUBLISHING_PLATFORMS

REQUIRED_FIELDS = {
    "mastodon": ("mastodon_base_url", "mastodon_access_token"),
    "bluesky": ("bluesky_handle", "bluesky_app_password"),
    "wordpress": ("wordpress_site_id", "wordpress_access_token"),
    "tumblr": ("tumblr_blog_identifier", "tumblr_access_token"),
    "telegram": ("telegram_bot_token", "telegram_channel_username"),
}


def platform_options(settings: Settings) -> list[dict]:
    def present(field: str) -> bool:
        value = getattr(settings, field)
        return bool((value.get_secret_value() if isinstance(value, SecretStr) else value).strip())

    options = []
    for platform in PUBLISHING_PLATFORMS:
        enabled = platform in settings.posting_platforms
        fields = REQUIRED_FIELDS[platform]
        if platform == "tumblr" and settings.tumblr_auto_refresh:
            fields = (
                "tumblr_blog_identifier", "tumblr_client_id", "tumblr_client_secret",
                "mongodb_uri", "token_encryption_key",
            )
        configured = all(present(field) for field in fields)
        options.append(
            {
                "platform": platform,
                "available": enabled and configured,
                "reason": ""
                if enabled and configured
                else ("Not enabled on server" if not enabled else "Credentials not configured"),
            }
        )
    return options
