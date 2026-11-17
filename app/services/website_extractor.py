"""Bounded static HTML extraction; JavaScript is not executed."""

import asyncio
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from app.utils.validators import (
    Resolver,
    WebsiteError,
    normalize_website_url,
    resolve_addresses,
    validate_destination,
)


class ExtractedWebsite(BaseModel):
    requested_url: str
    final_url: str
    title: str
    meta_description: str
    headings: list[str]
    text: str
    truncated: bool


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_html(
    content: bytes, requested_url: str, final_url: str, max_text_chars: int
) -> ExtractedWebsite:
    soup = BeautifulSoup(content, "html.parser")
    title = clean_text(soup.title.get_text(" "))[:500] if soup.title else ""
    description = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    meta_description = clean_text(str(description.get("content", "")))[:1000] if description else ""
    for element in soup(["script", "style", "noscript", "template", "nav", "footer", "svg"]):
        element.decompose()
    # Hidden elements are not evidence of visible website copy.
    for element in soup.select('[hidden], [aria-hidden="true"]'):
        if element.parent is not None:
            element.decompose()
    body = soup.body or soup
    headings = list(dict.fromkeys(
        clean_text(heading.get_text(" "))[:300] for heading in body.find_all(["h1", "h2", "h3"])
    ))
    lines = list(dict.fromkeys(
        line for part in body.get_text("\n").splitlines() if (line := clean_text(part))
    ))
    text = "\n".join(lines)
    if not text:
        raise WebsiteError("empty_content", "The website did not contain usable text.")
    return ExtractedWebsite(
        requested_url=requested_url,
        final_url=final_url,
        title=title,
        meta_description=meta_description,
        headings=[heading for heading in headings if heading][:50],
        text=text[:max_text_chars],
        truncated=len(text) > max_text_chars,
    )


class WebsiteExtractor:
    def __init__(
        self,
        *,
        timeout_seconds: float = 10,
        max_response_bytes: int = 1_000_000,
        max_text_chars: int = 24_000,
        max_redirects: int = 3,
        resolver: Resolver = resolve_addresses,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if (
            timeout_seconds <= 0
            or max_response_bytes <= 0
            or max_text_chars <= 0
            or max_redirects < 0
        ):
            raise ValueError("Extraction limits must be positive; redirects may be zero.")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.max_text_chars = max_text_chars
        self.max_redirects = max_redirects
        self.resolver = resolver
        self.transport = transport

    async def extract(self, value: str) -> ExtractedWebsite:
        try:
            # This deadline includes DNS, redirects, and reading the entire body.
            async with asyncio.timeout(self.timeout_seconds):
                return await self._extract(value)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise WebsiteError(
                "website_timeout", "The website did not respond within the deadline."
            ) from exc
        except httpx.HTTPError as exc:
            raise WebsiteError(
                "website_unavailable", "The website could not be fetched securely."
            ) from exc

    async def _extract(self, value: str) -> ExtractedWebsite:
        current = value
        requested_url = ""
        visited: set[str] = set()
        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
            # Different hostnames can share a pinned IP; do not reuse their TLS sessions.
            limits=httpx.Limits(max_keepalive_connections=0),
        ) as client:
            for hop in range(self.max_redirects + 1):
                destination = await validate_destination(current, self.resolver)
                current = str(destination.url)
                if not requested_url:
                    requested_url = current
                if current in visited:
                    raise WebsiteError("redirect_loop", "The website redirects in a loop.")
                visited.add(current)
                # Connect to the validated IP, with no second hostname DNS lookup.
                # Host and SNI preserve virtual-host routing and TLS certificate checks.
                async with client.stream(
                    "GET",
                    destination.connect_url,
                    headers={
                        "Host": destination.url.netloc.decode("ascii"),
                        "User-Agent": "DxoraAssignment/0.1 WebsiteAnalyzer",
                        "Accept": "text/html,application/xhtml+xml",
                        "Accept-Encoding": "identity",
                    },
                    extensions={"sni_hostname": destination.url.host},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location or hop == self.max_redirects:
                            raise WebsiteError(
                                "redirect_limit", "The website redirect limit was reached."
                            )
                        try:
                            next_url = normalize_website_url(urljoin(current, location))
                        except ValueError as exc:
                            raise WebsiteError(
                                "invalid_redirect", "The website returned an invalid redirect."
                            ) from exc
                        if destination.url.scheme == "https" and next_url.scheme == "http":
                            raise WebsiteError(
                                "unsafe_redirect", "HTTPS to HTTP redirects are not allowed."
                            )
                        current = str(next_url)
                        continue
                    if response.status_code < 200 or response.status_code >= 300:
                        raise WebsiteError(
                            "website_http_error", "The website returned an unsuccessful status."
                        )
                    media_type = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    )
                    if media_type not in {"text/html", "application/xhtml+xml"}:
                        raise WebsiteError(
                            "unsupported_content", "The website must return HTML content."
                        )
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise WebsiteError(
                            "unsupported_encoding", "Compressed responses are not supported."
                        )
                    length = response.headers.get("content-length")
                    if length is not None:
                        try:
                            declared_size = int(length)
                        except ValueError as exc:
                            raise WebsiteError(
                                "invalid_response", "Invalid website content length."
                            ) from exc
                        if declared_size < 0:
                            raise WebsiteError(
                                "invalid_response", "Invalid website content length."
                            )
                        if declared_size > self.max_response_bytes:
                            raise WebsiteError(
                                "response_too_large", "The website response exceeds the size limit."
                            )
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > self.max_response_bytes:
                            raise WebsiteError(
                                "response_too_large", "The website response exceeds the size limit."
                            )
                        content.extend(chunk)
                    return extract_html(
                        bytes(content), requested_url, current, self.max_text_chars
                    )
        raise WebsiteError("redirect_limit", "The website redirect limit was reached.")
