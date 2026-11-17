"""Concurrent posting with isolated failures and no implicit publication retries."""

import asyncio
from collections.abc import Sequence
from datetime import timezone

from app.platforms.base import PUBLISHING_PLATFORMS, PlatformAdapter, PlatformError, PublishedPost
from app.schemas import PostingRequest, PostingResponse, PostingResult

ERROR_MESSAGES = {
    "integration_unavailable": "This platform integration is not implemented yet.",
    "missing_credentials": "Platform credentials are not configured on the server.",
    "authentication_failed": "The platform rejected the configured credentials.",
    "permission_denied": "The account does not have permission to publish here.",
    "rate_limited": "The platform rate limit was reached.",
    "provider_error": "The platform returned an error.",
    "invalid_response": "The platform returned an invalid publication response.",
    "outcome_uncertain": "Publication could not be confirmed; verify before retrying.",
}
TIMEOUT_MESSAGE = "Posting timed out; publication may have occurred. Verify before retrying."


class PostingService:
    def __init__(self, adapters: Sequence[PlatformAdapter], timeout_seconds: float = 15) -> None:
        names = [adapter.name for adapter in adapters]
        if not names or len(names) > 5 or len(set(names)) != len(names):
            raise ValueError("Configure one to five distinct posting platforms.")
        if any(name not in PUBLISHING_PLATFORMS for name in names):
            raise ValueError("Unknown posting platform.")
        if not 0 < timeout_seconds <= 60:
            raise ValueError("Posting timeout must be greater than zero and at most 60 seconds.")
        self.adapters = tuple(adapters)
        self.timeout_seconds = timeout_seconds

    async def post(self, request: PostingRequest) -> PostingResponse:
        # Bound concurrency to the five configured adapters, and preserve configured order.
        results = await asyncio.gather(
            *(self._publish(adapter, request.message, request.cta_url) for adapter in self.adapters)
        )
        return PostingResponse(
            success=all(result.status == "success" for result in results), results=list(results)
        )

    async def _publish(self, adapter: PlatformAdapter, message: str, cta_url: str) -> PostingResult:
        try:
            async with asyncio.timeout(self.timeout_seconds):
                post = await adapter.publish(message, cta_url)
                if not isinstance(post, PublishedPost):
                    raise PlatformError("invalid_response")
            published_at = post.published_at.astimezone(timezone.utc)
            return PostingResult(
                platform=adapter.name,
                status="success",
                posted_url=str(post.url),
                public_access=post.public_access,
                date=published_at.date().isoformat(),
                time=published_at.time().isoformat(),
                error=None if post.public_access else "Public access could not be verified.",
            )
        except TimeoutError:
            message = TIMEOUT_MESSAGE
        except PlatformError as exc:
            message = ERROR_MESSAGES.get(exc.code, "Publishing failed for this platform.")
        except Exception:
            # Do not return raw exceptions: HTTP errors can contain tokens or response bodies.
            message = "Publication could not be confirmed; verify before retrying."
        return PostingResult(
            platform=adapter.name,
            status="failed",
            posted_url=None,
            public_access=False,
            date=None,
            time=None,
            error=message,
        )
