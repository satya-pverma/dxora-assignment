import asyncio
import json
from datetime import datetime, timezone
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.platforms.base import PlatformError, PublishedPost
from app.platforms.bluesky import BlueskyAdapter, link_facet
from app.platforms.http import PlatformHTTP, contains_message, publication_time
from app.platforms.mastodon import MastodonAdapter
from app.platforms.wordpress import WordPressAdapter, message_html
from app.schemas import PostingRequest
from app.services.posting_service import PostingService

MESSAGE = "Discover our services https://example.com"
STAMP = "2026-11-17T12:00:00+00:00"
DID = "did:plc:example123"
URI = f"at://{DID}/app.bsky.feed.post/record123"


def settings(**kwargs):
    values = {
        "mastodon_base_url": "https://social.example.com",
        "mastodon_access_token": "mastodon-secret",
        "bluesky_pds_url": "https://pds.example.com",
        "bluesky_handle": "example.bsky.social",
        "bluesky_app_password": "app-password-secret",
        "wordpress_site_id": "123",
        "wordpress_access_token": "wordpress-secret",
    }
    return Settings(_env_file=None, **(values | kwargs))


async def public_dns(host, port):
    return ["93.184.216.34"]


def client(handler, resolver=public_dns):
    return PlatformHTTP(transport=httpx.MockTransport(handler), resolver=resolver)


@pytest.mark.parametrize(
    "origin",
    [
        "http://social.example.com",
        "https://user:password@social.example.com",
        "https://social.example.com/path",
        "https://social.example.com?query=1",
        "https://social.example.com#fragment",
        "https://social.example.com:8443",
    ],
)
def test_config_rejects_unsafe_origins(origin):
    with pytest.raises(ValidationError):
        settings(mastodon_base_url=origin)
    with pytest.raises(ValidationError):
        settings(bluesky_pds_url=origin)


def test_credentials_are_redacted_from_settings():
    representation = repr(settings())
    for secret in ("mastodon-secret", "app-password-secret", "wordpress-secret"):
        assert secret not in representation


def test_link_facets_use_utf8_offsets_and_leave_punctuation_out():
    message = "\U0001f600 Visit (https://example.com/docs)."
    facet = link_facet(message)
    start = facet["index"]["byteStart"]
    end = facet["index"]["byteEnd"]
    assert message.encode("utf-8")[start:end].decode() == "https://example.com/docs"
    assert facet["features"][0]["uri"] == "https://example.com/docs"


def test_wordpress_html_escapes_copy_and_makes_only_cta_clickable():
    html = message_html("A <script> & offer https://example.com?a=1&b=2.")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert 'href="https://example.com/?a=1&amp;b=2"' in html
    assert html.count("<a ") == 1
    assert html.endswith("</a>.")


@pytest.mark.parametrize("timestamp", [None, "bad", "2026-11-17T12:00:00"])
def test_provider_dates_require_timezone(timestamp):
    with pytest.raises(PlatformError):
        publication_time(timestamp)


def test_html_verification_checks_message_not_just_a_success_page():
    assert contains_message("<p>Discover our services https://example.com</p>", MESSAGE)
    assert not contains_message("<p>Sign in to view this post</p>", MESSAGE)
    assert not contains_message(None, MESSAGE)


def test_mastodon_publishes_once_then_verifies_without_token():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "social.example.com"
        assert request.extensions["sni_hostname"] == "social.example.com"
        data = {
            "id": "42",
            "url": "https://social.example.com/@example/42",
            "visibility": "public",
            "created_at": STAMP,
            "content": f"<p>{MESSAGE}</p>",
        }
        if request.method == "POST":
            assert json.loads(request.content) == {"status": MESSAGE, "visibility": "public"}
            assert request.headers["authorization"] == "Bearer mastodon-secret"
        else:
            assert request.url.path == "/api/v1/statuses/42"
            assert "authorization" not in request.headers
        return httpx.Response(200, json=data)

    response = asyncio.run(
        PostingService(
            [
                MastodonAdapter(settings(), client(handler)),
            ]
        ).post(PostingRequest(message=MESSAGE))
    )
    assert response.success is True
    assert response.results[0].public_access is True
    assert [request.method for request in requests] == ["POST", "GET"]


def test_wordpress_publishes_and_checks_anonymous_post_identity():
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["host"] == "public-api.wordpress.com"
        data = {
            "ID": 42,
            "URL": "https://example.wordpress.com/update/",
            "date": STAMP,
            "status": "publish",
            "content": f"<p>{MESSAGE}</p>",
        }
        if request.method == "POST":
            payload = json.loads(request.content)
            assert payload["status"] == "publish"
            assert '<a href="https://example.com/">https://example.com</a>' in payload["content"]
            assert request.url.path.endswith("/sites/123/posts/new/")
            assert request.headers["authorization"] == "Bearer wordpress-secret"
        else:
            assert request.url.path.endswith("/sites/123/posts/42/")
            assert "authorization" not in request.headers
        return httpx.Response(200, json=data)

    response = asyncio.run(
        PostingService(
            [
                WordPressAdapter(settings(), client(handler)),
            ]
        ).post(PostingRequest(message=MESSAGE))
    )
    assert response.results[0].public_access is True
    assert len(requests) == 2


def test_bluesky_authenticates_posts_and_verifies_on_public_appview():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path.endswith("createSession"):
            assert request.headers["host"] == "pds.example.com"
            assert "authorization" not in request.headers
            assert json.loads(request.content)["password"] == "app-password-secret"
            return httpx.Response(200, json={"did": DID, "accessJwt": "session-token"})
        if request.url.path.endswith("createRecord"):
            assert request.headers["host"] == "pds.example.com"
            assert request.headers["authorization"] == "Bearer session-token"
            payload = json.loads(request.content)
            assert payload["repo"] == DID
            assert payload["record"]["text"] == MESSAGE
            assert payload["record"]["facets"] == [link_facet(MESSAGE)]
            return httpx.Response(200, json={"uri": URI, "cid": "contentid"})
        assert request.headers["host"] == "public.api.bsky.app"
        assert "authorization" not in request.headers
        assert parse_qs(request.url.query.decode())["uris"] == [URI]
        return httpx.Response(200, json={"posts": [{"uri": URI, "record": {"text": MESSAGE}}]})

    response = asyncio.run(
        PostingService(
            [
                BlueskyAdapter(settings(), client(handler)),
            ]
        ).post(PostingRequest(message=MESSAGE))
    )
    assert response.results[0].public_access is True
    assert response.results[0].posted_url == f"https://bsky.app/profile/{DID}/post/record123"
    assert len(requests) == 3


@pytest.mark.parametrize("adapter_type", [MastodonAdapter, BlueskyAdapter, WordPressAdapter])
def test_missing_credentials_never_call_network(adapter_type):
    def never(request):
        pytest.fail("Missing credentials must not cause network calls")

    empty = settings(mastodon_access_token="", bluesky_app_password="", wordpress_access_token="")
    with pytest.raises(PlatformError) as error:
        asyncio.run(adapter_type(empty, client(never)).publish(MESSAGE, "https://example.com/"))
    assert error.value.code == "missing_credentials"


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "authentication_failed"),
        (403, "permission_denied"),
        (429, "rate_limited"),
        (500, "outcome_uncertain"),
        (302, "outcome_uncertain"),
    ],
)
def test_http_errors_are_sanitized_and_not_retried(status, code):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            status, headers={"location": "https://attacker.example"}, text="SECRET upstream body"
        )

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            client(handler).request(
                "POST",
                "https://social.example.com/publish",
                token="SECRET",
                publishing=True,
            )
        )
    assert error.value.code == code
    assert "SECRET" not in str(error.value)
    assert len(requests) == 1


@pytest.mark.parametrize("body", [b"invalid json", b"[]", b"x" * 256_001])
def test_malformed_write_response_is_an_uncertain_outcome(body):
    with pytest.raises(PlatformError) as error:
        asyncio.run(
            client(lambda request: httpx.Response(200, content=body)).request(
                "POST",
                "https://social.example.com/publish",
                publishing=True,
            )
        )
    assert error.value.code == "outcome_uncertain"


def test_private_dns_is_blocked_before_sending_credentials():
    async def private_dns(host, port):
        return ["127.0.0.1"]

    def never(request):
        pytest.fail("Private destination must not receive credentials")

    with pytest.raises(PlatformError) as error:
        asyncio.run(
            client(never, private_dns).request(
                "POST",
                "https://social.example.com/publish",
                token="SECRET",
                publishing=True,
            )
        )
    assert error.value.code == "invalid_configuration"


def test_visibility_failure_preserves_confirmed_post():
    def handler(request):
        if request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "id": "42",
                    "url": "https://social.example.com/@example/42",
                    "visibility": "public",
                    "created_at": STAMP,
                },
            )
        return httpx.Response(403, text="Private upstream details")

    response = asyncio.run(
        PostingService(
            [
                MastodonAdapter(settings(), client(handler)),
            ]
        ).post(PostingRequest(message=MESSAGE))
    )
    result = response.results[0]
    assert result.status == "success"
    assert result.posted_url is not None
    assert result.public_access is False
    assert result.error == "Public access could not be verified."


def test_malformed_publication_details_are_not_reported_as_success():
    with pytest.raises(PlatformError) as error:
        asyncio.run(
            MastodonAdapter(
                settings(), client(lambda request: httpx.Response(200, json={"id": "42"}))
            ).publish(MESSAGE, "https://example.com/")
        )
    assert error.value.code == "outcome_uncertain"


def test_verification_deadline_preserves_confirmed_url():
    class Confirmed(MastodonAdapter):
        async def publish(self, message, cta_url):
            return PublishedPost(
                url="https://example.com/post/42",
                public_access=False,
                published_at=datetime.now(timezone.utc),
            )

        async def verify_public(self, post, message, cta_url):
            raise TimeoutError

    response = asyncio.run(
        PostingService([Confirmed(settings())]).post(PostingRequest(message=MESSAGE))
    )
    assert response.results[0].status == "success"
    assert response.results[0].posted_url == "https://example.com/post/42"
    assert response.results[0].public_access is False
