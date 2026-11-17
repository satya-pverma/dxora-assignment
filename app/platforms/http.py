"""Bounded JSON requests with pinned public destinations and no proxy/redirect trust."""

import json
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from pydantic import TypeAdapter

from app.platforms.base import PlatformError
from app.utils.validators import Resolver, WebsiteError, resolve_addresses, validate_destination

DATE_ADAPTER = TypeAdapter(datetime)


def require_text(data: dict, key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlatformError("invalid_response")
    return value


def publication_time(value) -> datetime:
    try:
        result = DATE_ADAPTER.validate_python(value)
        if result.utcoffset() is None:
            raise ValueError
        return result
    except (ValueError, TypeError) as exc:
        raise PlatformError("invalid_response") from exc


def contains_message(html: str, message: str) -> bool:
    if not isinstance(html, str):
        return False
    text = BeautifulSoup(html, "html.parser").get_text(" ")
    return " ".join(message.split()) in " ".join(text.split())


class PlatformHTTP:
    def __init__(
        self,
        timeout_seconds: float = 10,
        transport: httpx.AsyncBaseTransport | None = None,
        resolver: Resolver = resolve_addresses,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.resolver = resolver

    async def request(
        self,
        method: str,
        url: str,
        *,
        token: str | None = None,
        payload: dict | None = None,
        publishing: bool = False,
    ) -> dict:
        try:
            destination = await validate_destination(url, self.resolver)
            if destination.url.scheme != "https":
                raise PlatformError("invalid_configuration")
            headers = {
                "Host": destination.url.netloc.decode("ascii"),
                "Accept": "application/json",
                "Accept-Encoding": "identity",
                "User-Agent": "DxoraAssignment/0.1",
            }
            if token:
                headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                transport=self.transport,
                limits=httpx.Limits(max_keepalive_connections=0),
            ) as client:
                async with client.stream(
                    method,
                    destination.connect_url,
                    headers=headers,
                    json=payload,
                    extensions={"sni_hostname": destination.url.host},
                ) as response:
                    if response.status_code == 401:
                        raise PlatformError("authentication_failed")
                    if response.status_code == 403:
                        raise PlatformError("permission_denied")
                    if response.status_code == 429:
                        raise PlatformError("rate_limited")
                    if not 200 <= response.status_code < 300:
                        # A write can have taken effect even if an upstream gateway fails.
                        raise PlatformError("outcome_uncertain" if publishing else "provider_error")
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise PlatformError("invalid_response")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > 256_000:
                            raise PlatformError("invalid_response")
                        body.extend(chunk)
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError
            return result
        except WebsiteError as exc:
            code = (
                "invalid_configuration"
                if exc.code in {"invalid_url", "blocked_destination"}
                else "provider_error"
            )
            raise PlatformError(code) from exc
        except (httpx.HTTPError, OSError) as exc:
            raise PlatformError("outcome_uncertain" if publishing else "provider_error") from exc
        except (ValueError, UnicodeError) as exc:
            raise PlatformError("outcome_uncertain" if publishing else "invalid_response") from exc
        except PlatformError as exc:
            if publishing and exc.code == "invalid_response":
                raise PlatformError("outcome_uncertain") from exc
            raise
