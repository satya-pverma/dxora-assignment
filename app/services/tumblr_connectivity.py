"""Credential-free GET probes of a fixed Tumblr endpoint; no OAuth mutations."""

import ipaddress
import socket
import time

import httpx

URL = "https://api.tumblr.com/v2/oauth2/token"


def check_tumblr_connectivity(transport=None, resolve=socket.getaddrinfo) -> dict:
    checks = []
    targets = [("hostname", URL, False)]
    try:
        addresses = resolve("api.tumblr.com", 443, socket.AF_INET, socket.SOCK_STREAM)
        address = next(
            row[4][0] for row in addresses if ipaddress.ip_address(row[4][0]).is_global
        )
        targets.append(("ipv4", str(httpx.URL(URL).copy_with(host=address)), False))
    except (OSError, ValueError, StopIteration):
        checks.append({"mode": "ipv4", "reachable": False, "stage": "dns"})
    targets.append(("hostname_http2", URL, True))
    for mode, target, http2 in targets:
        started = time.monotonic()
        stage = "connect"

        def trace(name, info):
            nonlocal stage
            # Event details may contain headers: never read or return them.
            phases = {
                "connection.connect_tcp.started": "connect",
                "connection.start_tls.started": "tls",
                "http11.send_request_headers.started": "send_headers",
                "http11.receive_response_headers.started": "receive_headers",
                "http2.send_request_headers.started": "send_headers",
                "http2.receive_response_headers.started": "receive_headers",
            }
            stage = phases.get(name, stage)

        try:
            with httpx.Client(
                timeout=8, trust_env=False, follow_redirects=False, transport=transport,
                http2=http2,
            ) as client:
                with client.stream(
                    "GET", target, headers={"Host": "api.tumblr.com"},
                    extensions={"sni_hostname": "api.tumblr.com", "trace": trace},
                ) as response:
                    checks.append({
                        "mode": mode, "reachable": True, "http_status": response.status_code,
                        "http_version": response.http_version,
                        "elapsed_seconds": round(time.monotonic() - started, 2),
                    })
        except httpx.HTTPError as exc:
            checks.append({
                "mode": mode, "reachable": False, "stage": stage,
                "exception_type": type(exc).__name__,
                "elapsed_seconds": round(time.monotonic() - started, 2),
            })
    return {"checks": checks, "note": "GET only. No credentials, refresh or publication."}
