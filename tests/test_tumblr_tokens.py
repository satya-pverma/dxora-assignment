import asyncio
import copy
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import httpx
import pytest
from cryptography.fernet import Fernet, InvalidToken
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

from app.config import Settings
from app.platforms.base import PlatformError
from app.platforms.tumblr import TumblrAdapter
from app.services.platform_selection import platform_options
from app.services.tumblr_tokens import TumblrTokenStore, refresh_tumblr, storage_error_code


class Collection:
    def __init__(self):
        self.doc = None
        self.lock = threading.Lock()
        self.fail_save = False

    def find_one(self, query):
        with self.lock:
            return copy.deepcopy(self.doc)

    def update_one(self, query, update, upsert=False):
        with self.lock:
            if self.doc is None and upsert:
                self.doc = {"_id": query["_id"], **copy.deepcopy(update["$setOnInsert"])}
                return SimpleNamespace(modified_count=0)
            if self.doc is None or any(self.doc.get(k) != v for k, v in query.items()):
                return SimpleNamespace(modified_count=0)
            if "$setOnInsert" in update:
                return SimpleNamespace(modified_count=0)
            if self.fail_save and update.get("$set", {}).get("access_token"):
                raise RuntimeError("database failed")
            self.doc.update(copy.deepcopy(update.get("$set", {})))
            for key, value in update.get("$inc", {}).items():
                self.doc[key] += value
            for key in update.get("$unset", {}):
                self.doc.pop(key, None)
            return SimpleNamespace(modified_count=1)


@pytest.mark.parametrize(("error", "code"), [
    (InvalidToken(), "token_encryption_mismatch"),
    (OperationFailure("private", code=18), "token_database_auth_failed"),
    (OperationFailure("private", code=13), "token_database_permission_denied"),
    (ServerSelectionTimeoutError("private"), "token_database_unreachable"),
    (ConfigurationError("private"), "token_storage_configuration_invalid"),
    (ValueError("private"), "token_storage_configuration_invalid"),
])
def test_storage_errors_are_classified_without_private_details(error, code):
    assert storage_error_code(error) == code


@pytest.fixture
def settings():
    return Settings(
        _env_file=None, tumblr_auto_refresh=True, tumblr_blog_identifier="testblog",
        tumblr_client_id="test-client", tumblr_client_secret="test-secret",
        tumblr_access_token="old-access", tumblr_refresh_token="old-refresh",
        mongodb_uri="mongodb://unused", token_encryption_key=Fernet.generate_key().decode(),
    )


def test_refresh_persists_encrypted_rotated_pair_and_survives_restart(settings):
    collection = Collection()
    calls = []

    def refresh(token):
        calls.append(token)
        return {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": 2520}

    store = TumblrTokenStore(settings, collection, refresh, clock=lambda: 1000)
    assert store.get_token() == "new-access"
    assert calls == ["old-refresh"]
    assert "new-access" not in repr(collection.doc)
    assert "new-refresh" not in repr(collection.doc)
    assert store.cipher.decrypt(collection.doc["refresh_token"].encode()) == b"new-refresh"
    restarted = TumblrTokenStore(settings, collection, refresh, clock=lambda: 1001)
    restarted.seed()  # Old env tokens must never overwrite the stored rotation.
    assert restarted.get_token() == "new-access"
    assert len(calls) == 1
    # Near expiry, the next refresh consumes the latest persisted refresh token.
    restarted.clock = lambda: 3500
    assert restarted.get_token() == "new-access"
    assert calls == ["old-refresh", "new-refresh"]


def test_concurrent_workers_refresh_only_once(settings):
    collection = Collection()
    entered, release = threading.Event(), threading.Event()
    calls = []

    def refresh(token):
        calls.append(token)
        entered.set()
        assert release.wait(2)
        return {"access_token": "new", "refresh_token": "rotated", "expires_in": 2520}

    def work():
        return TumblrTokenStore(settings, collection, refresh).get_token()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(work)
        assert entered.wait(2)
        second = pool.submit(work)
        release.set()
        assert first.result() == second.result() == "new"
    assert calls == ["old-refresh"]


@pytest.mark.parametrize("failure", ["refresh", "save", "invalid"])
def test_uncertain_rotation_does_not_replay_old_tokens(settings, failure):
    collection = Collection()
    calls = []

    def refresh(token):
        calls.append(token)
        if failure == "refresh":
            raise RuntimeError("private response")
        if failure == "invalid":
            return {"access_token": "new"}
        return {"access_token": "new", "refresh_token": "rotated", "expires_in": 2520}

    collection.fail_save = failure == "save"
    store = TumblrTokenStore(settings, collection, refresh)
    for _ in range(2):
        with pytest.raises(PlatformError) as error:
            store.get_token()
        assert error.value.code == "token_refresh_response_invalid"
        assert "private response" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(("oauth_error", "expected"), [
    ("invalid_client", "token_refresh_client_rejected"),
    ("invalid_grant", "token_refresh_grant_rejected"),
])
def test_refresh_reports_allowlisted_oauth_failure(settings, monkeypatch, oauth_error, expected):
    original_client = httpx.Client

    def handler(request):
        return httpx.Response(400, json={
            "error": oauth_error, "error_description": "private-upstream-value",
        })

    monkeypatch.setattr(
        "app.services.tumblr_tokens.httpx.Client",
        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(handler)),
    )
    collection = Collection()
    store = TumblrTokenStore(settings, collection)
    with pytest.raises(PlatformError) as error:
        store.get_token()
    assert error.value.code == expected
    assert collection.doc["last_error"] == expected
    assert "private-upstream-value" not in repr(collection.doc)
    with pytest.raises(PlatformError) as blocked:
        store.get_token()
    assert blocked.value.code == expected


def test_abandoned_refresh_is_not_stolen(settings):
    collection = Collection()
    store = TumblrTokenStore(settings, collection, lambda _: pytest.fail("must not refresh"))
    store.seed()
    collection.doc.update(state="refreshing", refresh_started=0)
    with pytest.raises(PlatformError, match="reauthorization_required"):
        store.get_token()


def test_connect_timeout_keeps_refresh_token_retryable(settings):
    collection = Collection()
    calls = []

    def refresh(token):
        calls.append(token)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("private connection details")
        return {"access_token": "new", "refresh_token": "rotated", "expires_in": 2520}

    store = TumblrTokenStore(settings, collection, refresh)
    with pytest.raises(PlatformError, match="token_refresh_network_failed"):
        store.get_token()
    assert collection.doc["state"] == "ready"
    assert store.get_token() == "new"
    assert calls == ["old-refresh", "old-refresh"]


def test_wrong_encryption_key_does_not_claim_record(settings):
    collection = Collection()
    store = TumblrTokenStore(settings, collection)
    store.seed()
    other = settings.model_copy(update={
        "token_encryption_key": type(settings.token_encryption_key)(Fernet.generate_key().decode())
    })
    with pytest.raises(InvalidToken):
        TumblrTokenStore(other, collection).get_token()
    assert collection.doc["state"] == "ready"


def test_dashboard_accepts_database_mode_without_stale_bootstrap_token(settings):
    settings.tumblr_access_token = type(settings.tumblr_access_token)("")
    settings.tumblr_refresh_token = type(settings.tumblr_refresh_token)("")
    option = next(o for o in platform_options(settings) if o["platform"] == "tumblr")
    assert option["available"] is True


@pytest.mark.parametrize("http2", [False, True])
def test_refresh_endpoint_uses_form_body_and_no_redirects(settings, monkeypatch, http2):
    settings.tumblr_refresh_http2 = http2
    captured = []
    original_client = httpx.Client

    def handler(request):
        captured.append(request)
        assert request.url == "https://api.tumblr.com/v2/oauth2/token"
        assert b"grant_type=refresh_token" in request.content
        assert b"refresh_token=old-refresh" in request.content
        return httpx.Response(200, json={
            "access_token": "new", "refresh_token": "rotated", "expires_in": 2520,
        })

    def client(**kwargs):
        assert kwargs["trust_env"] is False
        assert kwargs["follow_redirects"] is False
        assert kwargs["http2"] is http2
        return original_client(**kwargs, transport=httpx.MockTransport(handler))

    monkeypatch.setattr("app.services.tumblr_tokens.httpx.Client", client)
    assert refresh_tumblr(settings, "old-refresh")["refresh_token"] == "rotated"
    assert len(captured) == 1


def test_adapter_publishes_once_using_stored_access_token(settings, monkeypatch):
    calls = []

    async def token_provider(config):
        return "stored-access"

    class HTTP:
        async def request(self, method, url, **kwargs):
            calls.append(kwargs)
            return {"meta": {"status": 201}, "response": {"id": "123"}}

    monkeypatch.setattr("app.platforms.tumblr.get_tumblr_token", token_provider)
    adapter = TumblrAdapter(settings, HTTP())
    result = asyncio.run(adapter.publish("Test https://example.com", "https://example.com"))
    assert str(result.url) == "https://testblog.tumblr.com/post/123"
    assert len(calls) == 1
    assert calls[0]["token"] == "stored-access"


def test_unexpected_token_error_is_safe_and_never_posts(settings, monkeypatch, caplog):
    async def broken_token(config):
        raise RuntimeError("private-credential-value")

    class HTTP:
        async def request(self, *args, **kwargs):
            pytest.fail("Must not publish after token acquisition fails")

    monkeypatch.setattr("app.platforms.tumblr.get_tumblr_token", broken_token)
    with pytest.raises(PlatformError, match="token_storage_unavailable"):
        asyncio.run(TumblrAdapter(settings, HTTP()).publish("Test https://example.com", ""))
    assert "exception_type=RuntimeError" in caplog.text
    assert "private-credential-value" not in caplog.text
