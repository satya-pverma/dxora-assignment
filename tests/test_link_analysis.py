import asyncio
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app, get_analysis_service
from app.schemas import ModelAnalysis
from app.services.analysis_service import AnalysisService
from app.services.llm_service import LLMError, LLMService, provider_schema
from app.services.website_extractor import ExtractedWebsite, WebsiteExtractor
from app.utils.validators import WebsiteError


@pytest.fixture
def model_result() -> dict:
    return {
        "brand": {
            "name": "Example Studio",
            "category": "Design",
            "summary": "Web design studio.",
            "products_and_services": ["Web design"],
        },
        "analysis": {
            "competitor_analysis": {
                "brand_overview": "Small design studio.",
                "competitors": [],
                "strengths": ["Design focus"],
                "competitive_advantages": [],
                "opportunities": ["Publish case studies"],
            },
            "target_search_queries": [
                {
                    "query": query,
                    "platforms": [platform],
                    "intent": "Find design services",
                    "business_relevance": "Design",
                    "target_audience": "Small businesses",
                }
                for query, platform in zip(
                    [
                        "web design studio",
                        "local website designers",
                        "website design ideas",
                        "business website design",
                        "small business design services",
                    ],
                    ["Google", "Facebook", "Instagram", "LinkedIn", "X"],
                    strict=True,
                )
            ],
            "seo_improvements": {
                "primary_keyword": "web design",
                "secondary_keywords": ["website studio"],
                "long_tail_keywords": ["website design for businesses"],
                "business_keywords": ["design services"],
                "recommended_title": "Example Studio | Web Design",
                "title_rationale": "Names the service and brand.",
                "meta_description": "Explore web design from Example Studio.",
                "supporting_content": ["Design case studies"],
            },
            "top_services": [
                {
                    "name": name,
                    "description": "Website-related service.",
                    "target_industry": "Small business",
                    "target_customer": "Business owners",
                    "main_benefit": "Improve online presence",
                    "evidence_type": "observed" if index == 0 else "inferred_recommendation",
                    "source_quote": "We offer web design." if index == 0 else None,
                }
                for index, name in enumerate(
                    [
                        "Web design",
                        "SEO audit",
                        "Maintenance",
                        "Brand design",
                        "Accessibility audit",
                    ]
                )
            ],
            "target_audience": {
                "primary_audience": ["Small businesses"],
                "secondary_audience": [],
                "industries": ["Professional services"],
                "business_types": ["Startups"],
                "customer_profiles": ["Owners needing a website"],
                "geographical_focus": None,
                "customer_needs": ["Online presence"],
                "interests": ["Design"],
                "marketing_segments": ["New businesses"],
            },
        },
    }


def completed(result: dict) -> dict:
    return {
        "status": "completed",
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": json.dumps(result)},
                ],
            }
        ],
        "usage": {"input_tokens": 800, "output_tokens": 1200},
    }


def settings(**kwargs) -> Settings:
    return Settings(_env_file=None, openai_api_key="test-key-never-live", **kwargs)


def website() -> ExtractedWebsite:
    return ExtractedWebsite(
        requested_url="https://example.com/",
        final_url="https://example.com/about",
        title="Example Studio",
        meta_description="Design",
        headings=["Services"],
        text="We offer web design.",
        truncated=False,
    )


@pytest.fixture(autouse=True)
def reset_dependencies():
    yield
    app.dependency_overrides.clear()


def test_provider_schema_has_required_fields_and_no_extra_properties():
    def visit(node):
        if isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(provider_schema())


def test_provider_receives_bounded_structured_request(model_result):
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.headers["authorization"] == "Bearer test-key-never-live"
        payload = json.loads(request.content)
        assert payload["store"] is False
        assert payload["max_output_tokens"] == 6000
        assert payload["text"]["format"]["strict"] is True
        assert "untrusted data" in payload["instructions"]
        assert "We offer web design." in payload["input"][0]["content"]
        assert "tools" not in payload
        return httpx.Response(200, json=completed(model_result))

    result, usage = asyncio.run(
        LLMService(settings(), httpx.MockTransport(handler)).analyze(website())
    )
    assert result.brand.name == "Example Studio"
    assert usage == {"input_tokens": 800, "output_tokens": 1200}


@pytest.mark.parametrize(
    ("status", "code", "api_status"),
    [
        (401, "llm_auth_error", 503),
        (403, "llm_auth_error", 503),
        (429, "llm_rate_limited", 503),
        (500, "llm_provider_error", 502),
        (302, "llm_provider_error", 502),
    ],
)
def test_provider_errors_are_sanitized(status, code, api_status):
    def handler(request):
        return httpx.Response(status, text="private upstream details test-key-never-live")

    with pytest.raises(LLMError) as error:
        asyncio.run(LLMService(settings(), httpx.MockTransport(handler)).analyze(website()))
    assert error.value.code == code
    assert error.value.status_code == api_status
    assert "private" not in str(error.value)
    assert "test-key" not in str(error.value)


@pytest.mark.parametrize(
    ("data", "code"),
    [
        ({"status": "incomplete", "output": []}, "llm_incomplete"),
        ({"status": "failed"}, "llm_incomplete"),
        ({"status": "completed", "output": []}, "llm_invalid_output"),
        ({"status": "completed", "output": [None]}, "llm_invalid_output"),
        (
            {
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "refusal", "refusal": "private details"},
                        ],
                    }
                ],
            },
            "llm_refused",
        ),
        (completed({"brand": {}}), "llm_invalid_output"),
    ],
)
def test_rejects_incomplete_refused_and_malformed_output(data, code):
    def handler(request):
        return httpx.Response(200, json=data)

    with pytest.raises(LLMError) as error:
        asyncio.run(LLMService(settings(), httpx.MockTransport(handler)).analyze(website()))
    assert error.value.code == code


@pytest.mark.parametrize("body", [b"invalid json", b"[]", b"x" * 256_001])
def test_rejects_bad_or_oversized_provider_body(body):
    with pytest.raises(LLMError) as error:
        asyncio.run(
            LLMService(
                settings(), httpx.MockTransport(lambda request: httpx.Response(200, content=body))
            ).analyze(website())
        )
    assert error.value.code == "llm_invalid_output"


def test_timeout_is_bounded():
    async def handler(request):
        await asyncio.sleep(1)
        return httpx.Response(200, json={})

    with pytest.raises(LLMError) as error:
        asyncio.run(
            LLMService(settings(llm_timeout_seconds=0.01), httpx.MockTransport(handler)).analyze(
                website()
            )
        )
    assert error.value.code == "llm_timeout"
    assert error.value.status_code == 504


@pytest.mark.parametrize("mutation", ["queries", "platforms", "services", "quote", "volumes"])
def test_rejects_invalid_analysis_contract(model_result, mutation):
    data = copy.deepcopy(model_result)
    analysis = data["analysis"]
    if mutation == "queries":
        analysis["target_search_queries"].pop()
    elif mutation == "platforms":
        analysis["target_search_queries"][0]["platforms"] = ["X"]
    elif mutation == "services":
        analysis["top_services"].pop()
    elif mutation == "quote":
        analysis["top_services"][0]["source_quote"] = None
    else:
        analysis["target_search_queries"][0]["search_volume"] = 9999
    with pytest.raises(ValidationError):
        ModelAnalysis.model_validate(data)


def setup_api(model_result, monkeypatch, extraction_error=None):
    async def extract(self, url):
        if extraction_error:
            raise extraction_error
        return website()

    monkeypatch.setattr(WebsiteExtractor, "extract", extract)
    service = AnalysisService(
        WebsiteExtractor(),
        LLMService(
            settings(),
            httpx.MockTransport(lambda request: httpx.Response(200, json=completed(model_result))),
        ),
    )
    app.dependency_overrides[get_analysis_service] = lambda: service


def test_endpoint_returns_all_sections_and_evidence_warnings(model_result, monkeypatch):
    setup_api(model_result, monkeypatch)
    with TestClient(app) as client:
        response = client.post("/link-analysis", json={"url": "https://example.com/"})
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert len(data["analysis"]) == 5
    assert data["metadata"]["source_url"] == "https://example.com/about"
    assert data["metadata"]["output_tokens"] == 1200
    assert len(data["metadata"]["warnings"]) == 4


def test_rejects_fabricated_service_quote(model_result, monkeypatch):
    model_result["analysis"]["top_services"][0]["source_quote"] = "We build spacecraft."
    setup_api(model_result, monkeypatch)
    with TestClient(app) as client:
        response = client.post("/link-analysis", json={"url": "https://example.com"})
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "llm_unsupported_claim"


@pytest.mark.parametrize(
    ("code", "status"),
    [
        ("blocked_destination", 400),
        ("website_timeout", 504),
        ("dns_error", 502),
    ],
)
def test_endpoint_maps_website_failures(model_result, monkeypatch, code, status):
    setup_api(model_result, monkeypatch, WebsiteError(code, "Website error"))
    with TestClient(app) as client:
        response = client.post("/link-analysis", json={"url": "https://example.com"})
    assert response.status_code == status
    assert response.json() == {
        "success": False,
        "error": {"code": code, "message": "Website error"},
    }


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"url": "file:///secret"},
        {"url": "http://localhost"},
        {"url": "https://example.com", "unexpected": True},
    ],
)
def test_endpoint_validates_request_before_work(body):
    def unexpected_service():
        class Unexpected:
            async def analyze(self, url):
                pytest.fail("Invalid input must not be processed")

        return Unexpected()

    app.dependency_overrides[get_analysis_service] = unexpected_service
    with TestClient(app) as client:
        response = client.post("/link-analysis", json=body)
    assert response.status_code == 422


def test_missing_credentials_fail_without_fetch(monkeypatch):
    async def extract(self, url):
        pytest.fail("Missing credentials must not cause a fetch")

    monkeypatch.setattr(WebsiteExtractor, "extract", extract)
    service = AnalysisService(
        WebsiteExtractor(), LLMService(Settings(_env_file=None, openai_api_key=""))
    )
    app.dependency_overrides[get_analysis_service] = lambda: service
    with TestClient(app) as client:
        response = client.post("/link-analysis", json={"url": "https://example.com"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "llm_not_configured"


def test_settings_redact_credentials():
    assert "test-key-never-live" not in repr(settings())
