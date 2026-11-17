"""Bounded JSON requests with pinned public destinations and no proxy/redirect trust."""

import json
from datetime import datetime

import httpx
from bs4 import BeautifulSoup
from pydantic import TypeAdapter

from app.platforms.base import PlatformError
from app.utils.validators import Resolver, WebsiteError, resolve_addresses, validate_destination

DATE_ADAPTER = TypeAdapter(datetime)


class SecretPathTransport(httpx.AsyncBaseTransport):
    """Insert Telegram's secret path below HTTPX's request logging layer."""

    def __init__(self, inner: httpx.AsyncBaseTransport, path: str) -> None:
        self.inner = inner
        self.path = path

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        actual = httpx.Request(
            request.method,
            request.url.copy_with(path=self.path),
            headers=request.headers,
            stream=request.stream,
            extensions=request.extensions,
        )
        try:
            return await self.inner.handle_async_request(actual)
        except Exception:
            # Do not expose exceptions carrying the actual secret-bearing request URL.
            raise httpx.TransportError("The platform transport failed.") from None

    async def aclose(self) -> None:
        await self.inner.aclose()


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
        secret_path: str | None = None,
        as_html: bool = False,
    ) -> dict | str:
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
            transport = self.transport
            if secret_path is not None:
                if destination.url.host != "api.telegram.org" or destination.url.path not in {
                    "/botredacted/getChat",
                    "/botredacted/sendMessage",
                }:
                    raise PlatformError("invalid_configuration")
                transport = SecretPathTransport(
                    transport or httpx.AsyncHTTPTransport(trust_env=False), secret_path
                )
            if as_html:
                headers["Accept"] = "text/html"
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                trust_env=False,
                follow_redirects=False,
                transport=transport,
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
                    if as_html:
                        media_type = response.headers.get("content-type", "").split(";", 1)[0]
                        if media_type.strip().lower() not in {"text/html", "application/xhtml+xml"}:
                            raise PlatformError("invalid_response")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(body) + len(chunk) > 256_000:
                            raise PlatformError("invalid_response")
                        body.extend(chunk)
            if as_html:
                return body.decode("utf-8", errors="replace")
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

    async def get_html(self, url: str) -> str:
        result = await self.request("GET", url, as_html=True)
        if not isinstance(result, str):
            raise PlatformError("invalid_response")
        return result
