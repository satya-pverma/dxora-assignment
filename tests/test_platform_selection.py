import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import DashboardPostingRequest, PostingRequest
from app.services.platform_selection import platform_options


def test_only_enabled_platforms_with_credentials_are_available():
    settings = Settings(
        _env_file=None,
        posting_platforms=["telegram", "mastodon"],
        telegram_bot_token="123:secret-token",
        telegram_channel_username="examplechannel",
        bluesky_handle="example.bsky.social",
        bluesky_app_password="secret-password",
    )
    options = {item["platform"]: item for item in platform_options(settings)}
    assert options["telegram"]["available"] is True
    assert options["mastodon"]["available"] is False
    assert options["bluesky"]["available"] is False
    assert "secret" not in str(options)


@pytest.mark.parametrize("platforms", [[], ["telegram", "telegram"], ["unknown"]])
def test_invalid_selections_are_rejected(platforms):
    with pytest.raises(ValidationError):
        DashboardPostingRequest(message="Hello https://example.com", platforms=platforms)


def test_assignment_endpoint_contract_still_rejects_client_selection():
    with pytest.raises(ValidationError):
        PostingRequest(message="Hello https://example.com", platforms=["telegram"])


def test_valid_selection_keeps_cta_validation():
    body = DashboardPostingRequest(message="Hello https://example.com", platforms=["telegram"])
    assert body.cta_url == "https://example.com/"
    with pytest.raises(ValidationError):
        DashboardPostingRequest(message="Missing CTA", platforms=["telegram"])
