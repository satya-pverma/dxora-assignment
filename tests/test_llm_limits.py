import asyncio
import json

import httpx
import pytest

from app.config import Settings
from app.services.llm_service import LLMError, LLMService, classify_limit_error


@pytest.mark.parametrize(
    "provider_code,public_code",
    [
        ("insufficient_quota", "llm_quota_exceeded"),
        ("credit_balance_exhausted", "llm_credit_balance_exhausted"),
        ("project_spend_limit_exceeded", "llm_project_spend_limit"),
        ("organization_spend_limit_exceeded", "llm_organization_spend_limit"),
        ("organization_usage_limit_exceeded", "llm_organization_usage_limit"),
        ("rate_limit_exceeded", "llm_rate_limited"),
        ("slow_down", "llm_rate_limited"),
    ],
)
def test_known_limit_codes_are_distinct_and_sanitized(provider_code, public_code):
    body = json.dumps({"error": {"code": provider_code, "message": "SECRET account details"}})
    error = classify_limit_error(body.encode())
    assert error.code == public_code
    assert error.status_code == 503
    assert "SECRET" not in str(error)


def test_quota_type_fallback_does_not_override_specific_spend_code():
    error = classify_limit_error(
        json.dumps(
            {
                "error": {
                    "type": "insufficient_quota",
                    "code": "project_spend_limit_exceeded",
                }
            }
        ).encode()
    )
    assert error.code == "llm_project_spend_limit"
    error = classify_limit_error(b'{"error":{"type":"insufficient_quota"}}')
    assert error.code == "llm_quota_exceeded"


@pytest.mark.parametrize(
    "body",
    [
        b"not json",
        b"[]",
        b"null",
        b'"text"',
        b'{"error":[]}',
        b'{"error":{"code":{},"message":"SECRET"}}',
    ],
)
def test_unknown_limit_bodies_are_safe(body):
    error = classify_limit_error(body)
    assert error.code == "llm_rate_limited"
    assert "SECRET" not in str(error)


@pytest.mark.parametrize(
    "body,expected",
    [
        (b'{"error":{"code":"insufficient_quota"}}', "llm_quota_exceeded"),
        (b"x" * 8193, "llm_rate_limited"),
    ],
)
def test_provider_429_body_is_bounded_and_classified(body, expected):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, content=body)

    service = LLMService(
        Settings(_env_file=None, openai_api_key="fake-key"), httpx.MockTransport(handler)
    )
    with pytest.raises(LLMError) as error:
        asyncio.run(service._request({}))
    assert error.value.code == expected
    assert len(calls) == 1
