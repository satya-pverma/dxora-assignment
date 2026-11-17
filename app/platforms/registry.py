from app.config import Settings
from app.platforms.base import PlatformAdapter, PublishingPlatform, UnavailableAdapter
from app.platforms.bluesky import BlueskyAdapter
from app.platforms.mastodon import MastodonAdapter
from app.platforms.wordpress import WordPressAdapter


def build_adapters(
    platforms: list[PublishingPlatform], settings: Settings | None = None
) -> list[PlatformAdapter]:
    settings = settings if settings is not None else Settings(_env_file=None)
    available = {
        "mastodon": MastodonAdapter,
        "bluesky": BlueskyAdapter,
        "wordpress": WordPressAdapter,
    }
    return [
        available[name](settings) if name in available else UnavailableAdapter(name)
        for name in platforms
    ]
