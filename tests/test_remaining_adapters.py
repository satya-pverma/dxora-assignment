import asyncio
import json
import logging
from html import escape

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.platforms.base import PUBLISHING_PLATFORMS, PlatformError
from app.platforms.http import PlatformHTTP
from app.platforms.registry import build_adapters
from app.platforms.telegram import TelegramAdapter, verify_telegram_html
from app.platforms.tumblr import TumblrAdapter, npf_text, verify_tumblr_html
from app.schemas import PostingRequest
from app.services.posting_service import PostingService

MESSAGE = "Discover our services https://example.com"
TOKEN = "123456:fake-bot-token"
CHAT = {"id": -100123456, "type": "channel", "username": "examplechannel"}


def settings(**kwargs):
    values = {
        "mastodon_base_url": "https://social.example.com",
        "mastodon_access_token": "fake-mastodon",
        "bluesky_handle": "example.bsky.social",
        "bluesky_app_password": "fake-bluesky",
        "wordpress_site_id": "123",
        "wordpress_access_token": "fake-wordpress",
        "tumblr_blog_identifier": "exampleblog",
        "tumblr_access_token": "fake-tumblr",
        "telegram_bot_token": TOKEN,
        "telegram_channel_username": "examplechannel",
        "telegram_channel_id": "",
    }
    return Settings(_env_file=None, **(values | kwargs))


async def public_dns(host, port):
    return ["93.184.216.34"]


def client(handler):
    return PlatformHTTP(transport=httpx.MockTransport(handler), resolver=public_dns)


def telegram_html(message=MESSAGE, post_id=42, username="examplechannel"):
    return (
        f'<div class="tgme_widget_message" data-post="{username}/{post_id}">'
        f'<div class="tgme_widget_message_text">{escape(message)}</div></div>'
    )


def tumblr_html(message=MESSAGE, post_id="42", blog="exampleblog.tumblr.com"):
    return f'<link rel="canonical" href="https://{blog}/post/{post_id}"><p>{escape(message)}</p>'


@pytest.mark.parametrize(
    "value",
    [
        "https://example.com",
        "../evil",
        "user@example.com",
        "-blog",
        "blog..tumblr.com",
        "example.com",
    ],
)
def test_rejects_invalid_tumblr_blog(value):
    with pytest.raises(ValidationError):
        settings(tumblr_blog_identifier=value)


def test_normalizes_tumblr_blog_and_public_channel_username():
    result = settings(
        tumblr_blog_identifier="ExampleBlog.TUMBLR.COM", telegram_channel_username="@ExampleChannel"
    )
    assert result.tumblr_blog_identifier == "exampleblog.tumblr.com"
    assert result.telegram_channel_username == "examplechannel"


@pytest.mark.parametrize(
    "field,value",
    [
        ("telegram_bot_token", "123:secret/path"),
        ("telegram_bot_token", "bad-token"),
        ("telegram_channel_id", "123"),
        ("telegram_channel_id", "@examplechannel"),
        ("telegram_channel_username", "https://t.me/examplechannel"),
        ("telegram_channel_username", "short!"),
    ],
)
def test_rejects_invalid_telegram_configuration(field, value):
    with pytest.raises(ValidationError):
        settings(**{field: value})


def test_bot_token_is_redacted_in_configuration_and_validation_errors():
    assert TOKEN not in repr(settings())
    secret = "123:secret/path"
    with pytest.raises(ValidationError) as error:
        settings(telegram_bot_token=secret)
    assert secret not in str(error.value)


def test_npf_link_uses_codepoints_and_preserves_unicode_copy():
    message = "\U0001f600 See (https://example.com/docs)."
    block = npf_text(message)
    formatting = block["formatting"][0]
    assert block["text"] == message
    assert message[formatting["start"] : formatting["end"]] == "https://example.com/docs"
    assert formatting["start"] == len("\U0001f600 See (")


@pytest.mark.parametrize(
    "html",
    [
        tumblr_html("Different message"),
        tumblr_html(post_id="43"),
        tumblr_html(blog="otherblog.tumblr.com"),
        f"<p>{MESSAGE}</p>",
    ],
)
def test_tumblr_visibility_requires_correct_canonical_and_copy(html):
    assert not verify_tumblr_html(html, "https://exampleblog.tumblr.com/post/42", MESSAGE)


def test_tumblr_visibility_accepts_permalink_slug():
    html = tumblr_html().replace('/post/42"', '/post/42/update"')
    assert verify_tumblr_html(html, "https://exampleblog.tumblr.com/post/42", MESSAGE)


@pytest.mark.parametrize(
    "html",
    [
        telegram_html("Different message"),
        telegram_html(post_id=43),
        telegram_html(username="otherchannel"),
        f"<p>{MESSAGE}</p>",
    ],
)
def test_telegram_visibility_requires_correct_widget_and_copy(html):
    assert not verify_telegram_html(html, "examplechannel", 42, MESSAGE)


def test_tumblr_creates_public_npf_post_and_verifies_without_auth():
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "POST":
            assert request.headers["host"] == "api.tumblr.com"
            assert request.url.path == "/v2/blog/exampleblog.tumblr.com/posts"
            assert request.headers["authorization"] == "Bearer fake-tumblr"
            payload = json.loads(request.content)
            assert payload["state"] == "published"
            assert payload["send_to_twitter"] is False
            assert payload["content"] == [npf_text(MESSAGE)]
            return httpx.Response(201, json={"meta": {"status": 201}, "response": {"id": "42"}})
        assert request.headers["host"] == "exampleblog.tumblr.com"
        assert request.url.path == "/post/42"
        assert "authorization" not in request.headers
        return httpx.Response(200, headers={"content-type": "text/html"}, text=tumblr_html())

    result = asyncio.run(
        PostingService([TumblrAdapter(settings(), client(handler))]).post(
            PostingRequest(message=MESSAGE)
        )
    )
    assert result.success is True
    assert result.results[0].public_access is True
    assert result.results[0].posted_url == "https://exampleblog.tumblr.com/post/42"
    assert len(calls) == 2


def test_telegram_checks_channel_publishes_once_and_hides_token_in_httpx_logs(caplog):
    caplog.set_level(logging.INFO, logger="httpx")
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.host == "93.184.216.34"
        if request.headers["host"] == "api.telegram.org":
            assert request.url.path.startswith(f"/bot{TOKEN}/")
            assert "authorization" not in request.headers
            payload = json.loads(request.content)
            if request.url.path.endswith("getChat"):
                assert payload == {"chat_id": "@examplechannel"}
                return httpx.Response(200, json={"ok": True, "result": CHAT})
            assert payload["chat_id"] == CHAT["id"]
            assert payload["text"] == MESSAGE
            assert "parse_mode" not in payload and "allow_paid_broadcast" not in payload
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "chat": CHAT,
                        "message_id": 42,
                        "date": 1794916800,
                        "text": MESSAGE,
                    },
                },
            )
        assert request.headers["host"] == "t.me"
        assert TOKEN not in str(request.url)
        return httpx.Response(200, headers={"content-type": "text/html"}, text=telegram_html())

    result = asyncio.run(
        PostingService([TelegramAdapter(settings(), client(handler))]).post(
            PostingRequest(message=MESSAGE)
        )
    )
    assert result.results[0].public_access is True
    assert result.results[0].posted_url == "https://t.me/examplechannel/42"
    assert len(calls) == 3
    assert TOKEN not in caplog.text


@pytest.mark.parametrize(
    "chat",
    [
        {"id": -100123456, "type": "group", "username": "examplechannel"},
        {"id": -100123456, "type": "channel"},
        {"id": -100123456, "type": "channel", "username": "differentchannel"},
    ],
)
def test_wrong_or_private_telegram_destination_is_rejected_before_publication(chat):
    calls = []

    def handler(request):
        calls.append(request)
        assert request.url.path.endswith("getChat")
        return httpx.Response(200, json={"ok": True, "result": chat})

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            TelegramAdapter(settings(), client(handler)).publish(MESSAGE, "https://example.com/")
        )
    assert error.value.code == "invalid_configuration"
    assert len(calls) == 1


def test_channel_numeric_id_must_match_preflight():
    adapter = TelegramAdapter(settings(telegram_channel_id="-10099999"))
    with pytest.raises(PlatformError):
        adapter._validate_chat(CHAT)


@pytest.mark.parametrize(
    "code,expected",
    [
        (401, "authentication_failed"),
        (403, "permission_denied"),
        (429, "rate_limited"),
        (500, "provider_error"),
    ],
)
def test_telegram_error_envelopes_are_sanitized(code, expected):
    def handler(request):
        return httpx.Response(
            200, json={"ok": False, "error_code": code, "description": f"secret {TOKEN}"}
        )

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            TelegramAdapter(settings(), client(handler)).publish(MESSAGE, "https://example.com/")
        )
    assert error.value.code == expected
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize("post_id", [None, "", "../42", "0", "x" * 100, 42])
def test_invalid_tumblr_confirmation_is_uncertain(post_id):
    def handler(request):
        return httpx.Response(201, json={"meta": {"status": 201}, "response": {"id": post_id}})

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            TumblrAdapter(settings(), client(handler)).publish(MESSAGE, "https://example.com/")
        )
    assert error.value.code == "outcome_uncertain"


@pytest.mark.parametrize(
    "adapter_type,overrides",
    [
        (TumblrAdapter, {"tumblr_access_token": ""}),
        (TelegramAdapter, {"telegram_bot_token": ""}),
        (TelegramAdapter, {"telegram_channel_username": ""}),
    ],
)
def test_missing_credentials_prevent_requests(adapter_type, overrides):
    def never(request):
        pytest.fail("Missing configuration must not call the network")

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            adapter_type(settings(**overrides), client(never)).publish(
                MESSAGE, "https://example.com/"
            )
        )
    assert error.value.code == "missing_credentials"


def test_telegram_transport_exceptions_do_not_expose_secret_path(caplog):
    caplog.set_level(logging.DEBUG)

    def handler(request):
        raise httpx.ConnectError(f"Failed {request.url}", request=request)

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            TelegramAdapter(settings(), client(handler)).publish(MESSAGE, "https://example.com/")
        )
    assert TOKEN not in str(error.value)
    assert TOKEN not in str(error.value.__cause__)
    assert TOKEN not in caplog.text


def test_all_five_adapters_are_registered():
    assert [
        adapter.name for adapter in build_adapters(list(PUBLISHING_PLATFORMS), settings())
    ] == list(PUBLISHING_PLATFORMS)
    assert all(
        type(adapter).__name__ != "UnavailableAdapter"
        for adapter in build_adapters(list(PUBLISHING_PLATFORMS), settings())
    )


def test_all_five_run_independently_when_some_platforms_fail():
    class FakeHTTP:
        async def request(self, method, url, **kwargs):
            if "social.example.com" in url:
                raise PlatformError("authentication_failed")
            if "wordpress.com" in url:
                raise PlatformError("permission_denied")
            if "createSession" in url:
                return {"did": "did:plc:example123", "accessJwt": "fake-session"}
            if "createRecord" in url:
                return {"uri": "at://did:plc:example123/app.bsky.feed.post/rkey", "cid": "cid"}
            if "getPosts" in url:
                return {
                    "posts": [
                        {
                            "uri": "at://did:plc:example123/app.bsky.feed.post/rkey",
                            "record": {"text": MESSAGE},
                        }
                    ]
                }
            if "api.tumblr.com" in url:
                return {"meta": {"status": 201}, "response": {"id": "42"}}
            if "getChat" in url:
                return {"ok": True, "result": {"id": -100123456, "type": "channel"}}
            pytest.fail(f"Unexpected request {url}")

        async def get_html(self, url):
            return tumblr_html()

    adapters = build_adapters(list(PUBLISHING_PLATFORMS), settings())
    for adapter in adapters:
        adapter.http = FakeHTTP()
    result = asyncio.run(PostingService(adapters).post(PostingRequest(message=MESSAGE)))
    assert result.success is False
    assert [item.status for item in result.results] == [
        "failed",
        "success",
        "failed",
        "success",
        "failed",
    ]
    assert result.results[1].public_access is True
    assert result.results[3].public_access is True
