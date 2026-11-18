"""Read-only Telegram setup checks. Never publishes or prints a bot token."""

import asyncio
import logging
import socket
import sys
import time

import httpx
from pydantic import ValidationError

from app.config import Settings


async def check_async_transport(settings: Settings) -> int:
    from app.platforms.http import SecretPathTransport
    from app.utils.validators import validate_destination

    token = settings.telegram_bot_token.get_secret_value()
    target = settings.telegram_channel_id or f"@{settings.telegram_channel_username}"
    if not token or not settings.telegram_channel_username:
        print("Set Telegram credentials first.")
        return 1

    async def trace(name, info):
        # Print event names only. Event details can contain credential-bearing URLs.
        if name.endswith(("started", "complete", "failed")):
            print(f"  {name}", flush=True)

    for mode in ("hostname", "pinned", "pinned + secret-path transport"):
        print(f"Checking async {mode} (read-only getChat):", flush=True)
        stage = "DNS"
        started = time.monotonic()
        try:
            async with asyncio.timeout(8):
                destination = await validate_destination(
                    "https://api.telegram.org/botredacted/getChat"
                )
                family = "IPv6" if ":" in destination.address else "IPv4"
                print(f"  DNS validated; selected {family}", flush=True)
                wrapped = mode == "pinned + secret-path transport"
                path = "/botredacted/getChat" if wrapped else f"/bot{token}/getChat"
                url = destination.url if mode == "hostname" else destination.connect_url
                transport = (
                    SecretPathTransport(
                        httpx.AsyncHTTPTransport(trust_env=False), f"/bot{token}/getChat"
                    )
                    if wrapped
                    else None
                )
                stage = "HTTPS request"
                async with httpx.AsyncClient(
                    timeout=7, trust_env=False, follow_redirects=False, transport=transport
                ) as client:
                    response = await client.post(
                        url.copy_with(path=path),
                        headers={"Host": "api.telegram.org", "Accept-Encoding": "identity"},
                        extensions={"sni_hostname": "api.telegram.org", "trace": trace},
                        json={"chat_id": target},
                    )
                    print(
                        f"  HTTP {response.status_code} in {time.monotonic() - started:.1f}s",
                        flush=True,
                    )
        except (TimeoutError, httpx.TimeoutException):
            print(f"  Timed out during {stage}.", flush=True)
        except Exception:
            print(
                f"  Failed during {stage}; exception details hidden to protect credentials.",
                flush=True,
            )
    print("Transport checks complete. No message was published.")
    return 0


def main() -> int:
    # Telegram puts credentials in the URL; suppress HTTP request logging.
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).disabled = True
    try:
        settings = Settings()
    except ValidationError:
        print("Invalid configuration. Run scripts.check_credentials to check field names.")
        return 1
    token = settings.telegram_bot_token.get_secret_value()
    username = settings.telegram_channel_username
    if not token or not username:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_USERNAME first.")
        return 1
    if "--transport" in sys.argv:
        return asyncio.run(check_async_transport(settings))

    def call(client, method, payload):
        try:
            response = client.post(f"https://api.telegram.org/bot{token}/{method}", json=payload)
            if response.status_code != 200:
                print(f"{method}: HTTP {response.status_code}. Check token/channel/permissions.")
                return None
            data = response.json()
            if data.get("ok") is not True or not isinstance(data.get("result"), dict):
                print(f"{method}: Telegram did not confirm the request.")
                return None
            print(f"{method}: OK")
            return data["result"]
        except httpx.TimeoutException:
            print(f"{method}: timed out. Check access to api.telegram.org on this network.")
        except httpx.HTTPError:
            print(f"{method}: connection failed. Check DNS, firewall, and network access.")
        except (ValueError, TypeError, AttributeError):
            print(f"{method}: unexpected Telegram response.")
        return None

    with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
        bot = call(client, "getMe", {})
        if bot is None:
            return 1
        chat = call(client, "getChat", {"chat_id": settings.telegram_channel_id or f"@{username}"})
        if chat is None:
            return 1
        if chat.get("type") != "channel" or str(chat.get("username", "")).lower() != username:
            print("The destination must be the configured public channel, not a group or bot.")
            return 1
        member = call(client, "getChatMember", {"chat_id": chat["id"], "user_id": bot["id"]})
        if member is None:
            return 1
        if member.get("status") != "creator" and not (
            member.get("status") == "administrator" and member.get("can_post_messages") is True
        ):
            print("Make the bot a channel administrator with Post Messages permission.")
            return 1
    print("Telegram setup checks passed. No message was published.")
    print("Checking the publisher's pinned connection (read-only getChat):")
    try:
        records = socket.getaddrinfo(
            "api.telegram.org", 443, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM
        )
        addresses = list(dict.fromkeys(record[4][0] for record in records))
    except OSError:
        print("Publisher connection: DNS lookup failed.")
        return 1
    from app.utils.validators import is_public_address

    if not addresses or not all(is_public_address(address) for address in addresses):
        print("Publisher connection: DNS did not return exclusively public addresses.")
        return 1
    print("The publisher prefers a validated public IPv4 address when available.")
    # Same IP pinning, Host header, SNI, and proxy policy as PlatformHTTP,
    # using a synchronous client so the check can isolate network behaviour.
    with httpx.Client(timeout=5, trust_env=False, follow_redirects=False) as client:
        for index, address in enumerate(addresses[:4]):
            family = "IPv6" if ":" in address else "IPv4"
            started = time.monotonic()
            try:
                response = client.post(
                    httpx.URL(f"https://api.telegram.org/bot{token}/getChat").copy_with(
                        host=address
                    ),
                    headers={"Host": "api.telegram.org", "Accept-Encoding": "identity"},
                    extensions={"sni_hostname": "api.telegram.org"},
                    json={"chat_id": settings.telegram_channel_id or f"@{username}"},
                )
                print(
                    f"DNS choice {index + 1} ({family}): HTTP {response.status_code} "
                    f"in {time.monotonic() - started:.1f}s"
                )
            except httpx.TimeoutException:
                print(f"DNS choice {index + 1} ({family}): connection timed out.")
            except httpx.HTTPError:
                print(f"DNS choice {index + 1} ({family}): connection failed.")
    print("Checks complete. No message was published.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
