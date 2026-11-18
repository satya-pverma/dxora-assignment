"""Encrypted MongoDB token rotation. No publication is performed here.

A refresh claim is never automatically reclaimed: after a crash or ambiguous
OAuth result, reauthorization is safer than replaying a possibly consumed token.
"""

import asyncio
import json
import logging
import time
from contextlib import contextmanager

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pymongo import MongoClient
from pymongo.errors import (
    ConfigurationError,
    ConnectionFailure,
    DuplicateKeyError,
    OperationFailure,
    PyMongoError,
)
from pymongo.write_concern import WriteConcern

from app.config import Settings
from app.platforms.base import PlatformError

logger = logging.getLogger(__name__)
REFRESH_FAILURES = {
    "token_refresh_client_rejected", "token_refresh_grant_rejected",
    "token_refresh_network_failed", "token_refresh_response_invalid",
    "token_refresh_failed", "token_storage_unavailable",
}


@contextmanager
def token_collection(settings: Settings):
    with MongoClient(
        settings.mongodb_uri.get_secret_value(),
        serverSelectionTimeoutMS=3000, connectTimeoutMS=3000, socketTimeoutMS=3000,
        timeoutMS=4000, retryWrites=True, tls=True,
    ) as client:
        yield client[settings.mongodb_database].get_collection(
            settings.mongodb_collection, write_concern=WriteConcern(w="majority", wtimeout=3000)
        )


def require_refresh_config(settings: Settings) -> None:
    if not all([
        settings.mongodb_uri.get_secret_value(), settings.tumblr_client_id.strip(),
        settings.tumblr_client_secret.get_secret_value(),
        settings.token_encryption_key.get_secret_value(), settings.tumblr_blog_identifier,
    ]):
        raise PlatformError("missing_credentials")


def refresh_tumblr(settings: Settings, refresh_token: str) -> dict:
    # Fixed HTTPS destination, form body credentials, no proxy/redirects/retries.
    with httpx.Client(timeout=8, trust_env=False, follow_redirects=False) as client:
        with client.stream(
            "POST", "https://api.tumblr.com/v2/oauth2/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token,
                  "client_id": settings.tumblr_client_id,
                  "client_secret": settings.tumblr_client_secret.get_secret_value()},
        ) as response:
            body = bytearray()
            for chunk in response.iter_bytes():
                if len(body) + len(chunk) > 16384:
                    raise PlatformError("token_refresh_failed")
                body.extend(chunk)
            if response.status_code != 200:
                logger.error("Tumblr refresh endpoint HTTP status=%s", response.status_code)
                try:
                    error = json.loads(body).get("error")
                except (ValueError, AttributeError):
                    error = None
                code = {
                    "invalid_client": "token_refresh_client_rejected",
                    "invalid_grant": "token_refresh_grant_rejected",
                }.get(error) if isinstance(error, str) else None
                raise PlatformError(code or "token_refresh_failed")
    try:
        return json.loads(body)
    except ValueError:
        raise PlatformError("token_refresh_response_invalid") from None


class TumblrTokenStore:
    def __init__(self, settings: Settings, collection, refresh=None, clock=time.time):
        self.settings = settings
        self.collection = collection
        self.refresh = refresh or (lambda token: refresh_tumblr(settings, token))
        self.clock = clock
        self.cipher = Fernet(settings.token_encryption_key.get_secret_value().encode())
        # Isolate credentials belonging to different Tumblr apps/blogs.
        self.record_id = f"tumblr:{settings.tumblr_client_id}:{settings.tumblr_blog_identifier}"

    def encrypt(self, token: str) -> str:
        return self.cipher.encrypt(token.encode()).decode()

    def seed(self, *, replace=False):
        if not self.settings.tumblr_refresh_token.get_secret_value().strip():
            raise PlatformError("missing_credentials")
        record = {
            "access_token": self.encrypt(self.settings.tumblr_access_token.get_secret_value()),
            "refresh_token": self.encrypt(self.settings.tumblr_refresh_token.get_secret_value()),
            # Unknown issuance time: refresh before first use instead of guessing.
            "expires_at": 0, "state": "ready", "version": 0,
        }
        if replace:
            self.collection.replace_one({"_id": self.record_id}, record, upsert=True)
        else:
            try:
                self.collection.update_one(
                    {"_id": self.record_id}, {"$setOnInsert": record}, upsert=True
                )
            except DuplicateKeyError:
                pass  # Another worker seeded the same unique _id.

    def get_token(self) -> str:
        for _ in range(11):
            record = self.collection.find_one({"_id": self.record_id})
            if record is None:
                self.seed()
                continue
            state = record.get("state")
            if state == "refreshing":
                if self.clock() - record.get("refresh_started", 0) > 60:
                    raise PlatformError("token_refresh_reauthorization_required")
                time.sleep(0.2)
                continue
            if state != "ready":
                failure = record.get("last_error")
                raise PlatformError(
                    failure if failure in REFRESH_FAILURES
                    else "token_refresh_reauthorization_required"
                )
            if record["expires_at"] > self.clock() + 90:
                return self.cipher.decrypt(record["access_token"].encode()).decode()
            # A configuration/key error must not poison an otherwise valid record.
            refresh_token = self.cipher.decrypt(record["refresh_token"].encode()).decode()
            # Atomic compare-and-set across processes, not just a Python lock.
            claimed = self.collection.update_one(
                {"_id": self.record_id, "version": record["version"], "state": "ready"},
                {"$set": {"state": "refreshing", "refresh_started": self.clock()}},
            )
            if not claimed.modified_count:
                continue
            try:
                tokens = self.refresh(refresh_token)
                if (
                    not isinstance(tokens, dict)
                    or not all(isinstance(tokens.get(k), str) and tokens[k].strip()
                               for k in ("access_token", "refresh_token"))
                    or type(tokens.get("expires_in")) is not int
                    or not 90 < tokens["expires_in"] <= 31536000
                ):
                    logger.error("Tumblr refresh response missing valid tokens or lifetime")
                    raise PlatformError("token_refresh_response_invalid")
                # Persist both replacements before allowing publication.
                saved = self.collection.update_one(
                    {"_id": self.record_id, "version": record["version"], "state": "refreshing"},
                    {"$set": {
                        "access_token": self.encrypt(tokens["access_token"]),
                        "refresh_token": self.encrypt(tokens["refresh_token"]),
                        "expires_at": self.clock() + tokens["expires_in"], "state": "ready",
                    }, "$inc": {"version": 1},
                     "$unset": {"refresh_started": "", "last_error": ""}},
                )
                if not saved.modified_count:
                    raise PlatformError("token_storage_unavailable")
                return tokens["access_token"]
            except Exception as exc:
                if isinstance(exc, httpx.TransportError):
                    failure = "token_refresh_network_failed"
                elif isinstance(exc, PyMongoError):
                    failure = "token_storage_unavailable"
                elif isinstance(exc, PlatformError) and exc.code in REFRESH_FAILURES:
                    failure = exc.code
                else:
                    failure = "token_refresh_response_invalid"
                logger.error("Tumblr renewal failed category=%s", failure)
                # Never silently revert to stale environment credentials or replay
                # an old refresh token after an ambiguous refresh/persistence result.
                try:
                    self.collection.update_one(
                        {"_id": self.record_id, "version": record["version"],
                         "state": "refreshing"},
                        {"$set": {"state": "reauthorize", "last_error": failure}},
                    )
                except PyMongoError:
                    pass
                raise PlatformError(failure) from None
        raise PlatformError("token_refresh_busy")


def storage_error_code(error: Exception) -> str:
    if isinstance(error, InvalidToken):
        return "token_encryption_mismatch"
    if isinstance(error, OperationFailure):
        if error.code == 18:
            return "token_database_auth_failed"
        if error.code == 13:
            return "token_database_permission_denied"
    if isinstance(error, ConnectionFailure):
        return "token_database_unreachable"
    if isinstance(error, (ConfigurationError, ValueError)):
        return "token_storage_configuration_invalid"
    return "token_storage_unavailable"


def stored_token(settings: Settings) -> str:
    require_refresh_config(settings)
    try:
        with token_collection(settings) as collection:
            return TumblrTokenStore(settings, collection).get_token()
    except PlatformError:
        raise
    except (PyMongoError, InvalidToken, ValueError, KeyError, TypeError) as exc:
        raise PlatformError(storage_error_code(exc)) from None


async def get_tumblr_token(settings: Settings) -> str:
    if not settings.tumblr_auto_refresh:
        return settings.tumblr_access_token.get_secret_value()
    # A cancelled publication may leave this thread running. It only refreshes and
    # persists credentials; it never posts, and can safely finish saving rotation.
    return await asyncio.to_thread(stored_token, settings)
