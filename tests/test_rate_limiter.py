from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_analysis_service
from app.services.rate_limiter import AnalysisRateLimiter, AnalysisRateLimitError


def test_two_requests_then_reject_with_retry_after():
    now = [100.0]
    limiter = AnalysisRateLimiter(clock=lambda: now[0])
    limiter.consume("alice")
    now[0] = 110
    limiter.consume("alice")
    now[0] = 111.2
    with pytest.raises(AnalysisRateLimitError) as error:
        limiter.consume("alice")
    assert error.value.retry_after == 49
    limiter.consume("bob")


def test_rolling_window_and_exact_expiry():
    now = [0.0]
    limiter = AnalysisRateLimiter(clock=lambda: now[0])
    limiter.consume("alice")
    now[0] = 30
    limiter.consume("alice")
    now[0] = 60
    limiter.consume("alice")
    with pytest.raises(AnalysisRateLimitError) as error:
        limiter.consume("alice")
    assert error.value.retry_after == 30
    now[0] = 90
    limiter.consume("alice")


def test_client_storage_is_bounded_without_resetting_active_clients():
    now = [0.0]
    limiter = AnalysisRateLimiter(clock=lambda: now[0], max_clients=1)
    limiter.consume("alice")
    with pytest.raises(AnalysisRateLimitError):
        limiter.consume("bob")
    now[0] = 60
    limiter.consume("bob")
    assert list(limiter._clients) == ["bob"]


def test_concurrent_requests_cannot_exceed_limit():
    limiter = AnalysisRateLimiter(clock=lambda: 0)

    def attempt(_):
        try:
            limiter.consume("alice")
            return True
        except AnalysisRateLimitError:
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(20))) == 2


def test_endpoint_blocks_third_request_before_analysis_and_ignores_spoofed_ip(monkeypatch):
    monkeypatch.setattr("app.main.get_settings", lambda: Settings(_env_file=None))
    calls = []

    class FakeService:
        async def analyze(self, url):
            calls.append(url)
            return JSONResponse({"success": True})

    app.dependency_overrides[get_analysis_service] = FakeService
    try:
        with TestClient(app) as client:
            for number in range(3):
                response = client.post(
                    "/link-analysis",
                    json={"url": "https://example.com"},
                    headers={"X-Forwarded-For": f"1.1.1.{number}"},
                )
                assert response.status_code == (200 if number < 2 else 429)
            assert response.json()["error"]["code"] == "analysis_rate_limited"
            assert 1 <= int(response.headers["Retry-After"]) <= 60
            assert len(calls) == 2
            assert client.get("/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_unauthorized_and_invalid_requests_do_not_consume_quota(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_settings", lambda: Settings(_env_file=None, demo_access_key="demo-test")
    )

    class FakeService:
        async def analyze(self, url):
            return JSONResponse({"success": True})

    app.dependency_overrides[get_analysis_service] = FakeService
    try:
        with TestClient(app) as client:
            for _ in range(3):
                assert (
                    client.post("/link-analysis", json={"url": "https://example.com"}).status_code
                    == 401
                )
                assert (
                    client.post(
                        "/link-analysis", json={"url": ""}, headers={"X-Demo-Key": "demo-test"}
                    ).status_code
                    == 422
                )
            for _ in range(2):
                assert (
                    client.post(
                        "/link-analysis",
                        json={"url": "https://example.com"},
                        headers={"X-Demo-Key": "demo-test"},
                    ).status_code
                    == 200
                )
    finally:
        app.dependency_overrides.clear()
