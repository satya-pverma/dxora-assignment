"""Validate public website destinations before making network requests."""

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx


class WebsiteError(ValueError):
    """A safe, caller-facing extraction failure with a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


Resolver = Callable[[str, int], Awaitable[list[str]]]


async def resolve_addresses(host: str, port: int) -> list[str]:
    records = await asyncio.get_running_loop().getaddrinfo(
        host, port, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
    )
    return list(dict.fromkeys(record[4][0] for record in records))


def normalize_website_url(value: str) -> httpx.URL:
    if not isinstance(value, str) or not value or len(value) > 2048:
        raise WebsiteError("invalid_url", "Provide an HTTP(S) website URL up to 2048 characters.")
    if any(ord(char) < 33 or ord(char) == 127 for char in value) or "\\" in value:
        raise WebsiteError("invalid_url", "URLs must not contain whitespace or backslashes.")
    try:
        url = httpx.URL(value)
        if url.scheme not in {"http", "https"} or not url.host or url.userinfo:
            raise ValueError
        expected_port = 443 if url.scheme == "https" else 80
        if url.port is not None and url.port != expected_port:
            raise ValueError
        host = url.host.lower().rstrip(".")
        if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError
        return url.copy_with(host=host, fragment=None)
    except (ValueError, httpx.InvalidURL) as exc:
        raise WebsiteError(
            "invalid_url", "Use an HTTP(S) URL without credentials on a standard web port."
        ) from exc


def is_public_address(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not address.is_global or address.is_multicast or "%" in value:
        return False
    if isinstance(address, ipaddress.IPv6Address):
        # Do not permit transition mechanisms to conceal an IPv4 destination.
        if address.ipv4_mapped or address.sixtofour or address.teredo:
            return False
    return True


@dataclass(frozen=True)
class PublicDestination:
    url: httpx.URL
    address: str

    @property
    def connect_url(self) -> httpx.URL:
        return self.url.copy_with(host=self.address)


async def validate_destination(
    value: str, resolver: Resolver = resolve_addresses
) -> PublicDestination:
    url = normalize_website_url(value)
    try:
        literal = ipaddress.ip_address(url.host)
    except ValueError:
        try:
            addresses = await resolver(url.host, url.port or (443 if url.scheme == "https" else 80))
        except OSError as exc:
            raise WebsiteError("dns_error", "The website hostname could not be resolved.") from exc
    else:
        addresses = [str(literal)]
    # Reject mixed public/private answers rather than choosing only the public one.
    if not addresses or not all(is_public_address(address) for address in addresses):
        raise WebsiteError(
            "blocked_destination", "Only publicly routable website addresses are allowed."
        )
    return PublicDestination(url=url, address=addresses[0])
