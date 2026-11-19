import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, connectivity_rate_limiter
from app.services.tumblr_connectivity import check_tumblr_connectivity


def test_probes_send_no_credentials_and_accept_http_error_responses():
    calls = []

    def handler(request):
        calls.append(request)
        assert request.method == "GET"
        assert "authorization" not in request.headers
        assert not request.content
        assert request.headers["host"] == "api.tumblr.com"
        return httpx.Response(405)

    result = check_tumblr_connectivity(
        httpx.MockTransport(handler),
        resolve=lambda *args: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    assert len(calls) == 2
    assert all(check["reachable"] and check["http_status"] == 405 for check in result["checks"])


def test_diagnostic_distinguishes_hostname_and_ipv4_without_exception_details():
    def handler(request):
        if request.url.host == "api.tumblr.com":
            raise httpx.ConnectTimeout("private diagnostic details")
        return httpx.Response(401)

    result = check_tumblr_connectivity(
        httpx.MockTransport(handler),
        resolve=lambda *args: [(None, None, None, None, ("8.8.8.8", 443))],
    )
    assert result["checks"][0]["exception_type"] == "ConnectTimeout"
    assert result["checks"][1]["reachable"]
    assert "private diagnostic details" not in str(result)


def test_endpoint_requires_key_and_limits_checks(monkeypatch):
    connectivity_rate_limiter.clear()
    monkeypatch.setattr(
        "app.main.get_settings", lambda: Settings(_env_file=None, demo_access_key="k"),
    )
    monkeypatch.setattr("app.main.check_tumblr_connectivity", lambda: {"checks": []})
    try:
        with TestClient(app) as client:
            assert client.get("/dashboard/diagnostics/tumblr").status_code == 401
            for _ in range(2):
                assert client.get(
                    "/dashboard/diagnostics/tumblr", headers={"x-demo-key": "k"},
                ).status_code == 200
            assert client.get(
                "/dashboard/diagnostics/tumblr", headers={"x-demo-key": "k"},
            ).status_code == 429
    finally:
        connectivity_rate_limiter.clear()
