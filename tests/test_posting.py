import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app, get_posting_service
from app.platforms.base import (
    PUBLISHING_PLATFORMS,
    PlatformAdapter,
    PlatformError,
    PublishedPost,
)
from app.platforms.registry import build_adapters
from app.schemas import PostingRequest
from app.services.posting_service import PostingService

MESSAGE = "Discover our services https://example.com"


class FakeAdapter(PlatformAdapter):
    def __init__(self, name="mastodon", *, error=None, delay=0, public=True, calls=None):
        self.name = name
        self.error = error
        self.delay = delay
        self.public = public
        self.calls = calls if calls is not None else []

    async def publish(self, message, cta_url):
        self.calls.append((self.name, message, cta_url))
        await asyncio.sleep(self.delay)
        if self.error:
            raise self.error
        return PublishedPost(
            url=f"https://example.com/posts/{self.name}",
            public_access=self.public,
            published_at=datetime(
                2026, 11, 17, 18, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))
            ),
        )


@pytest.mark.parametrize(
    "message",
    [
        "",
        " ",
        "No CTA",
        "https://",
        "https://.",
        "ftp://example.com",
        "https://example.com https://other.example.com",
        "https://example.com https://example.com",
        "https://example.com ftp://another.example.com",
        "https://user:password@example.com",
        "https://exa\\mple.com",
        "Read https://example.com\x00",
        "x" * 181 + " https://example.com",
    ],
)
def test_rejects_invalid_message(message):
    with pytest.raises(ValidationError):
        PostingRequest(message=message)


@pytest.mark.parametrize(
    ("message", "expected_url"),
    [
        (MESSAGE, "https://example.com/"),
        ("Read (https://example.com/about).", "https://example.com/about"),
        ("Read <https://example.com/about>!", "https://example.com/about"),
        ("Read https://example.com/docs_(v1)", "https://example.com/docs_(v1)"),
        ("Read HTTPS://EXAMPLE.COM?a=1&b=2", "https://example.com/?a=1&b=2"),
        ("Read https://example.com:8443/about", "https://example.com:8443/about"),
        ("Read\nhttps://example.com/about", "https://example.com/about"),
    ],
)
def test_accepts_one_cta_and_preserves_original_message(message, expected_url):
    request = PostingRequest(message=message)
    assert request.message == message
    assert request.cta_url == expected_url
    assert request.model_dump() == {"message": message}


def test_character_limit_counts_full_message_and_unicode():
    suffix = " https://example.com"
    message = "😀" * (200 - len(suffix)) + suffix
    assert len(message) == 200
    assert PostingRequest(message=message).message == message
    with pytest.raises(ValidationError):
        PostingRequest(message=message + "x")


def test_request_cannot_select_platforms():
    with pytest.raises(ValidationError):
        PostingRequest(message=MESSAGE, platforms=["mastodon"])


@pytest.mark.parametrize("platforms", [[], ["mastodon", "mastodon"], ["unknown"]])
def test_settings_reject_invalid_platform_selection(platforms):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, posting_platforms=platforms)


def test_settings_allow_internal_selection_and_order():
    settings = Settings(_env_file=None, posting_platforms=["telegram", "mastodon"])
    assert [adapter.name for adapter in build_adapters(settings.posting_platforms)] == [
        "telegram",
        "mastodon",
    ]


@pytest.mark.parametrize("timeout", [0, -1, 61])
def test_settings_bound_timeouts(timeout):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, posting_timeout_seconds=timeout)


def test_post_contract_rejects_naive_dates_and_url_credentials():
    with pytest.raises(ValidationError):
        PublishedPost(
            url="https://example.com/post", public_access=True, published_at=datetime(2026, 11, 17)
        )
    with pytest.raises(ValidationError):
        PublishedPost(
            url="https://user:password@example.com/post",
            public_access=True,
            published_at=datetime.now(timezone.utc),
        )


def test_service_rejects_empty_and_duplicate_adapters():
    with pytest.raises(ValueError):
        PostingService([])
    with pytest.raises(ValueError):
        PostingService([FakeAdapter(), FakeAdapter()])


def test_successful_results_preserve_order_and_use_utc():
    calls = []
    adapters = [
        FakeAdapter("telegram", delay=0.01, calls=calls),
        FakeAdapter("mastodon", calls=calls),
    ]
    response = asyncio.run(PostingService(adapters).post(PostingRequest(message=MESSAGE)))
    assert response.success is True
    assert [result.platform for result in response.results] == ["telegram", "mastodon"]
    assert len(calls) == 2
    assert all(call[1:] == (MESSAGE, "https://example.com/") for call in calls)
    assert all(result.status == "success" and result.error is None for result in response.results)
    assert response.results[0].date == "2026-11-17"
    assert response.results[0].time == "13:00:00"


def test_failure_does_not_stop_other_platforms_or_expose_secrets():
    adapters = [
        FakeAdapter("mastodon", error=RuntimeError("Bearer SECRET")),
        FakeAdapter("bluesky"),
        FakeAdapter("telegram", error=PlatformError("authentication_failed")),
    ]
    response = asyncio.run(PostingService(adapters).post(PostingRequest(message=MESSAGE)))
    assert response.success is False
    assert [result.status for result in response.results] == ["failed", "success", "failed"]
    assert "SECRET" not in response.model_dump_json()
    assert response.results[0].date is None
    assert response.results[0].posted_url is None
    assert response.results[2].error == "The platform rejected the configured credentials."


def test_timeout_does_not_block_success_or_retry():
    calls = []
    response = asyncio.run(
        PostingService(
            [
                FakeAdapter("mastodon", delay=1, calls=calls),
                FakeAdapter("bluesky", calls=calls),
            ],
            timeout_seconds=0.02,
        ).post(PostingRequest(message=MESSAGE))
    )
    assert response.results[0].status == "failed"
    assert "may have occurred" in response.results[0].error
    assert response.results[1].status == "success"
    assert len(calls) == 2


def test_concurrent_adapters_start_before_any_completion():
    started = set()

    class CoordinatedAdapter(FakeAdapter):
        async def publish(self, message, cta_url):
            started.add(self.name)
            while len(started) < 2:
                await asyncio.sleep(0)
            return await super().publish(message, cta_url)

    response = asyncio.run(
        PostingService(
            [
                CoordinatedAdapter("mastodon"),
                CoordinatedAdapter("bluesky"),
            ],
            timeout_seconds=1,
        ).post(PostingRequest(message=MESSAGE))
    )
    assert response.success is True


def test_public_verification_failure_preserves_published_url():
    response = asyncio.run(
        PostingService([FakeAdapter(public=False)]).post(PostingRequest(message=MESSAGE))
    )
    assert response.success is True
    result = response.results[0]
    assert result.status == "success"
    assert result.posted_url is not None
    assert result.public_access is False
    assert result.error == "Public access could not be verified."


def test_default_registry_returns_honest_failures_for_all_five_platforms():
    settings = Settings(
        _env_file=None,
        mastodon_base_url="",
        mastodon_access_token="",
        bluesky_handle="",
        bluesky_app_password="",
        wordpress_site_id="",
        wordpress_access_token="",
    )
    response = asyncio.run(
        PostingService(build_adapters(list(PUBLISHING_PLATFORMS), settings)).post(
            PostingRequest(message=MESSAGE)
        )
    )
    assert response.success is False
    assert len(response.results) == 5
    assert all(result.status == "failed" for result in response.results)
    assert all(result.posted_url is None for result in response.results)
    assert all("not configured" in result.error for result in response.results[:3])
    assert all("not implemented" in result.error for result in response.results[3:])


def test_unknown_adapter_error_codes_are_sanitized():
    response = asyncio.run(
        PostingService(
            [
                FakeAdapter(error=PlatformError("SECRET upstream body")),
            ]
        ).post(PostingRequest(message=MESSAGE))
    )
    assert "SECRET" not in response.model_dump_json()


def test_invalid_adapter_result_does_not_stop_other_platforms():
    class BrokenAdapter(FakeAdapter):
        async def publish(self, message, cta_url):
            return {"success": True}

    response = asyncio.run(
        PostingService(
            [
                BrokenAdapter("mastodon"),
                FakeAdapter("bluesky"),
            ]
        ).post(PostingRequest(message=MESSAGE))
    )
    assert response.results[0].error == "The platform returned an invalid publication response."
    assert response.results[1].status == "success"


@pytest.fixture
def client():
    try:
        app.dependency_overrides[get_posting_service] = lambda: PostingService(
            [
                FakeAdapter("mastodon"),
                FakeAdapter("bluesky", error=PlatformError("rate_limited")),
            ]
        )
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_posting_service, None)


def test_endpoint_returns_partial_results(client):
    response = client.post("/posting", json={"message": MESSAGE})
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["results"][0]["status"] == "success"
    assert response.json()["results"][1]["status"] == "failed"


@pytest.mark.parametrize(
    "body",
    [{}, {"message": "No link"}, {"message": 123}, {"message": MESSAGE, "platforms": ["telegram"]}],
)
def test_endpoint_rejects_bad_input_before_posting(client, body):
    class NeverPost:
        async def post(self, request):
            pytest.fail("Invalid requests must not publish")

    app.dependency_overrides[get_posting_service] = lambda: NeverPost()
    response = client.post("/posting", json=body)
    assert response.status_code == 422
