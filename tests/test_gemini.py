import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.config import Settings
from app.schemas import ModelAnalysis
from app.services.gemini_service import GeminiService, gemini_schema, parse_gemini_response
from app.services.llm_factory import build_llm_service
from app.services.llm_service import LLMError, LLMService
from app.services.website_extractor import ExtractedWebsite


def response():
    sample = json.loads(Path("docs/examples/link-analysis.response.json").read_text())
    result = {key: sample[key] for key in ("brand", "analysis")}
    return {
        "candidates": [
            {
                "finishReason": "STOP",
                "content": {
                    "parts": [
                        {"thought": True, "text": "private reasoning"},
                        {"text": json.dumps(result)},
                    ]
                },
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 20,
            "thoughtsTokenCount": 5,
        },
    }


def test_parse_valid_response_counts_thinking_tokens():
    result, usage = parse_gemini_response(response())
    assert isinstance(result, ModelAnalysis)
    assert usage == {"input_tokens": 10, "output_tokens": 25}


@pytest.mark.parametrize(
    "finish,code",
    [
        ("SAFETY", "llm_refused"),
        ("RECITATION", "llm_refused"),
        ("MAX_TOKENS", "llm_incomplete"),
        (None, "llm_incomplete"),
    ],
)
def test_finish_reason(finish, code):
    data = response()
    data["candidates"][0]["finishReason"] = finish
    with pytest.raises(LLMError) as error:
        parse_gemini_response(data)
    assert error.value.code == code


@pytest.mark.parametrize(
    "data",
    [{}, {"candidates": []}, {"candidates": [None]}, {"promptFeedback": {"blockReason": "SAFETY"}}],
)
def test_invalid_or_blocked_response(data):
    with pytest.raises(LLMError):
        parse_gemini_response(data)


def test_schema_expands_refs():
    schema = json.dumps(gemini_schema())
    assert '"$ref"' not in schema
    assert '"$defs"' not in schema
    assert '"const"' not in schema
    assert '"additionalProperties": false' in schema


def test_factory_and_credentials():
    assert isinstance(build_llm_service(Settings(_env_file=None)), LLMService)
    service = build_llm_service(Settings(_env_file=None, llm_provider="gemini"))
    assert isinstance(service, GeminiService)
    with pytest.raises(LLMError) as error:
        service.require_credentials()
    assert error.value.code == "llm_not_configured"


def test_mocked_request_contract():
    def handler(request):
        assert request.headers["x-goog-api-key"] == "fake-key"
        assert "fake-key" not in str(request.url)
        payload = json.loads(request.content)
        assert payload["generationConfig"]["responseMimeType"] == "application/json"
        assert "responseJsonSchema" in payload["generationConfig"]
        assert "tools" not in payload
        return httpx.Response(200, json=response())

    service = GeminiService(
        Settings(_env_file=None, gemini_api_key="fake-key"), httpx.MockTransport(handler)
    )
    website = ExtractedWebsite(
        requested_url="https://example.com",
        final_url="https://example.com",
        title="Example",
        meta_description="",
        headings=[],
        text="We offer web design.",
        truncated=False,
    )
    result, _ = asyncio.run(service.analyze(website))
    assert result.brand.name == "Example Studio"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 429, 500, 503])
def test_http_errors_do_not_expose_provider_body(status):
    service = GeminiService(
        Settings(_env_file=None, gemini_api_key="fake-key"),
        httpx.MockTransport(lambda request: httpx.Response(status, text="secret-provider-body")),
    )
    with pytest.raises(LLMError) as error:
        asyncio.run(service._request({}))
    assert "secret-provider-body" not in str(error.value)
