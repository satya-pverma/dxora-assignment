import asyncio

import httpx
import pytest

from app.services.website_extractor import WebsiteExtractor, extract_html
from app.utils.validators import WebsiteError, normalize_website_url, validate_destination


async def public_dns(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://example.com", "https://user:pass@example.com",
    "http://localhost", "http://service.internal", "https://example.com:8080",
    "https://example.com/ bad", "https://example.com\\@localhost", "", "https://",
])
def test_rejects_invalid_urls(url: str) -> None:
    with pytest.raises(WebsiteError, match="URL|HTTP"):
        normalize_website_url(url)


@pytest.mark.parametrize("address", [
    "127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "169.254.169.254",
    "100.64.0.1", "0.0.0.0", "224.0.0.1", "::1", "fc00::1", "fe80::1",
    "::ffff:127.0.0.1", "2002:7f00:1::",
])
def test_blocks_nonpublic_dns_and_ip_literals(address: str) -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return [address]

    with pytest.raises(WebsiteError) as error:
        asyncio.run(validate_destination("https://example.com", resolver))
    assert error.value.code == "blocked_destination"
    literal = f"[{address}]" if ":" in address else address
    with pytest.raises(WebsiteError):
        asyncio.run(validate_destination(f"http://{literal}"))


def test_rejects_mixed_dns_results() -> None:
    async def resolver(host: str, port: int) -> list[str]:
        return ["93.184.216.34", "10.0.0.1"]

    with pytest.raises(WebsiteError):
        asyncio.run(validate_destination("https://example.com", resolver))


def test_cleans_html_and_bounds_text() -> None:
    html = b"""<html><head><title> Our Brand </title>
    <meta name="description" content="Useful services"></head><body>
    <nav>Navigation</nav><script>bad()</script><h1>Services</h1><p>Web design</p>
    <p>Web design</p><p hidden>Secret</p><footer>Footer</footer></body></html>"""
    result = extract_html(html, "https://example.com", "https://example.com", 100)
    assert result.title == "Our Brand"
    assert result.meta_description == "Useful services"
    assert result.headings == ["Services"]
    assert result.text == "Services\nWeb design"
    assert not result.truncated
    assert extract_html(html, "x", "x", 5).truncated


def test_pins_connection_and_preserves_host_and_sni() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>Hello</p>")

    result = asyncio.run(WebsiteExtractor(
        resolver=public_dns, transport=httpx.MockTransport(handler)
    ).extract("https://example.com/#fragment"))
    assert result.final_url == "https://example.com/"
    assert result.text == "Hello"
    assert len(calls) == 1


def test_revalidates_redirects_before_connecting() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest"})

    with pytest.raises(WebsiteError) as error:
        asyncio.run(WebsiteExtractor(
            resolver=public_dns, transport=httpx.MockTransport(handler)
        ).extract("http://example.com"))
    assert error.value.code == "blocked_destination"
    assert len(calls) == 1


@pytest.mark.parametrize(("status", "headers", "body", "code"), [
    (403, {}, "blocked", "website_http_error"),
    (200, {"content-type": "application/json"}, "{}", "unsupported_content"),
    (200, {"content-type": "text/html", "content-length": "100"}, "x", "response_too_large"),
    (200, {"content-type": "text/html"}, "x" * 30, "response_too_large"),
    (200, {"content-type": "text/html"}, "", "empty_content"),
    (200, {"content-type": "text/html", "content-encoding": "br"}, "", "unsupported_encoding"),
    (302, {"location": "/next"}, "", "redirect_limit"),
])
def test_handles_failed_and_oversized_responses(status, headers, body, code) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, headers=headers, content=body.encode())

    with pytest.raises(WebsiteError) as error:
        asyncio.run(WebsiteExtractor(
            resolver=public_dns, transport=httpx.MockTransport(handler),
            max_response_bytes=20, max_redirects=0,
        ).extract("https://example.com"))
    assert error.value.code == code


def test_total_deadline_includes_dns() -> None:
    async def slow_dns(host: str, port: int) -> list[str]:
        await asyncio.sleep(1)
        return ["93.184.216.34"]

    with pytest.raises(WebsiteError) as error:
        asyncio.run(WebsiteExtractor(timeout_seconds=0.01, resolver=slow_dns).extract(
            "https://example.com"
        ))
    assert error.value.code == "website_timeout"


def test_follows_relative_redirect_and_rechecks_dns() -> None:
    resolved = []

    async def resolver(host: str, port: int) -> list[str]:
        resolved.append((host, port))
        return ["93.184.216.34"]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/":
            return httpx.Response(302, headers={"location": "/about"})
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<p>About</p>")

    result = asyncio.run(WebsiteExtractor(
        resolver=resolver, transport=httpx.MockTransport(handler)
    ).extract("https://example.com"))
    assert result.final_url == "https://example.com/about"
    assert resolved == [("example.com", 443), ("example.com", 443)]


@pytest.mark.parametrize(("location", "code"), [
    ("http://example.com/about", "unsafe_redirect"),
    ("https://example.com/", "redirect_loop"),
    ("file:///etc/passwd", "invalid_redirect"),
])
def test_rejects_unsafe_or_looping_redirects(location: str, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": location})

    with pytest.raises(WebsiteError) as error:
        asyncio.run(WebsiteExtractor(
            resolver=public_dns, transport=httpx.MockTransport(handler)
        ).extract("https://example.com/"))
    assert error.value.code == code


def test_dns_failure_has_safe_error() -> None:
    async def resolver(host: str, port: int) -> list[str]:
        raise OSError("internal resolver details")

    with pytest.raises(WebsiteError) as error:
        asyncio.run(validate_destination("https://example.com", resolver))
    assert error.value.code == "dns_error"
    assert "internal resolver" not in str(error.value)


def test_network_failure_has_safe_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("internal network details", request=request)

    with pytest.raises(WebsiteError) as error:
        asyncio.run(WebsiteExtractor(
            resolver=public_dns, transport=httpx.MockTransport(handler)
        ).extract("https://example.com"))
    assert error.value.code == "website_unavailable"
    assert "internal network" not in str(error.value)
