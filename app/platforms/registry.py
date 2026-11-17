from app.platforms.base import PlatformAdapter, PublishingPlatform, UnavailableAdapter


def build_adapters(platforms: list[PublishingPlatform]) -> list[PlatformAdapter]:
    # Real integrations replace these entries in subsequent feature PRs.
    return [UnavailableAdapter(name) for name in platforms]
