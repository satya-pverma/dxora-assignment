from app.config import Settings
from app.platforms.base import PlatformAdapter, PublishingPlatform
from app.platforms.bluesky import BlueskyAdapter
from app.platforms.mastodon import MastodonAdapter
from app.platforms.telegram import TelegramAdapter
from app.platforms.tumblr import TumblrAdapter
from app.platforms.wordpress import WordPressAdapter


def build_adapters(
    platforms: list[PublishingPlatform], settings: Settings | None = None
) -> list[PlatformAdapter]:
    settings = settings if settings is not None else Settings(_env_file=None)
    available = {
        "mastodon": MastodonAdapter,
        "bluesky": BlueskyAdapter,
        "wordpress": WordPressAdapter,
        "tumblr": TumblrAdapter,
        "telegram": TelegramAdapter,
    }
    return [available[name](settings) for name in platforms]
