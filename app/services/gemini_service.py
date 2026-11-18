"""Gemini generateContent adapter using the shared validated analysis contract."""

import asyncio
import json
import random

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.schemas import ModelAnalysis
from app.services.llm_service import QUOTE_REPAIR_PROMPT, SYSTEM_PROMPT, LLMError, provider_schema
from app.services.website_extractor import ExtractedWebsite


def gemini_schema(website: ExtractedWebsite | None = None) -> dict:
    schema = provider_schema(website)
    definitions = schema.get("$defs", {})

    def expand(node):
        if isinstance(node, list):
            return [expand(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].removeprefix("#/$defs/")
            return expand(definitions[name] | {k: v for k, v in node.items() if k != "$ref"})
        result = {
            key: expand(value) for key, value in node.items() if key not in {"$defs", "title"}
        }
        if "const" in result:
            result["enum"] = [result.pop("const")]
        return result

    return expand(schema)


def parse_gemini_response(data: dict) -> tuple[ModelAnalysis, dict]:
    try:
        feedback = data.get("promptFeedback") or {}
        if feedback.get("blockReason") not in {None, "BLOCK_REASON_UNSPECIFIED"}:
            raise LLMError("llm_refused", "Gemini declined this analysis.")
        candidates = data.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != 1:
            raise ValueError
        candidate = candidates[0]
        finish = candidate.get("finishReason")
        if finish in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
            raise LLMError("llm_refused", "Gemini declined this analysis.")
        if finish != "STOP":
            raise LLMError("llm_incomplete", "Gemini did not complete the analysis.")
        parts = candidate["content"]["parts"]
        if not isinstance(parts, list):
            raise ValueError
        texts = []
        for part in parts:
            if part.get("thought") is True:
                continue
            if not isinstance(part.get("text"), str):
                raise ValueError
            texts.append(part["text"])
        if not texts:
            raise ValueError
        result = ModelAnalysis.model_validate_json("".join(texts), strict=True)
        usage = data.get("usageMetadata") or {}

        def count(name, default=None):
            value = usage.get(name, default)
            return value if type(value) is int and value >= 0 else None

        candidates_count = count("candidatesTokenCount")
        thoughts_count = count("thoughtsTokenCount", 0)
        return result, {
            "input_tokens": count("promptTokenCount"),
            "output_tokens": (
                candidates_count + thoughts_count
                if candidates_count is not None and thoughts_count is not None
                else None
            ),
        }
    except (ValueError, TypeError, KeyError, AttributeError, ValidationError) as exc:
        if isinstance(exc, LLMError):
            raise
        detail = ""
        if isinstance(exc, ValidationError):
            # Expose schema-owned field names and error categories only, never values,
            # raw model JSON, arbitrary extra keys, or validator exception messages.
            schema = ModelAnalysis.model_json_schema()
            fields = set(schema.get("properties", {}))
            for definition in schema.get("$defs", {}).values():
                fields.update(definition.get("properties", {}))
            failures = []
            for error in exc.errors(include_input=False, include_context=False)[:3]:
                path = ".".join(
                    str(part) if isinstance(part, int) or part in fields else "field"
                    for part in error["loc"]
                ) or "response"
                failures.append(f"{path}: {error['type']}")
            detail = " Validation details: " + "; ".join(failures) + "."
        raise LLMError(
            "llm_invalid_output", "Gemini analysis did not match the required schema." + detail
        ) from exc


class RetryableGeminiError(LLMError):
    """A temporary upstream HTTP failure, safe to retry within the time budget."""


class GeminiService:
    provider = "gemini"

    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    @property
    def model(self) -> str:
        return self.settings.gemini_model

    def require_credentials(self) -> None:
        if not self.settings.gemini_api_key.get_secret_value().strip():
            raise LLMError("llm_not_configured", "Configure GEMINI_API_KEY on the server.", 503)

    async def analyze(
        self, website: ExtractedWebsite, *, repair_quotes: bool = False
    ) -> tuple[ModelAnalysis, dict]:
        self.require_credentials()
        generation = {
            "candidateCount": 1,
            "responseMimeType": "application/json",
            "responseJsonSchema": gemini_schema(website),
            "maxOutputTokens": self.settings.llm_max_output_tokens,
        }
        if self.model.startswith("gemini-3"):
            generation["thinkingConfig"] = {"thinkingLevel": "low"}
        payload = {
            "systemInstruction": {
                "parts": [{"text": SYSTEM_PROMPT + (QUOTE_REPAIR_PROMPT if repair_quotes else "")}]
            },
            "contents": [{"role": "user", "parts": [{"text": website.model_dump_json()}]}],
            "generationConfig": generation,
        }
        try:
            async with asyncio.timeout(self.settings.llm_timeout_seconds):
                data = await self._request(payload)
        except (TimeoutError, httpx.TimeoutException) as exc:
            raise LLMError("llm_timeout", "Gemini analysis timed out.", 504) from exc
        except httpx.HTTPError as exc:
            raise LLMError("llm_unavailable", "Gemini could not be reached.", 503) from exc
        return parse_gemini_response(data)

    async def _request(self, payload: dict) -> dict:
        for attempt in range(3):
            try:
                return await self._request_once(payload)
            except (RetryableGeminiError, httpx.TransportError):
                if attempt == 2:
                    raise
                await asyncio.sleep(2 ** attempt + random.uniform(0, 0.5))
        raise AssertionError("Unreachable retry state")

    async def _request_once(self, payload: dict) -> dict:
        async with httpx.AsyncClient(
            timeout=self.settings.llm_timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
        ) as client:
            async with client.stream(
                "POST",
                f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
                json=payload,
                headers={
                    "x-goog-api-key": self.settings.gemini_api_key.get_secret_value(),
                    "Accept-Encoding": "identity",
                },
            ) as response:
                if response.status_code in {500, 502, 503, 504}:
                    raise RetryableGeminiError(
                        "llm_unavailable",
                        "Gemini is temporarily unavailable. Please try again shortly.",
                        503,
                    )
                errors = {
                    400: (
                        "llm_request_rejected",
                        "Gemini rejected the request; check model/schema support.",
                        502,
                    ),
                    401: ("llm_auth_error", "Gemini rejected the configured API key.", 503),
                    403: (
                        "llm_auth_error",
                        "Gemini access denied; check key and project verification.",
                        503,
                    ),
                    404: (
                        "llm_model_unavailable",
                        "The configured Gemini model is unavailable.",
                        503,
                    ),
                    429: (
                        "llm_rate_limited",
                        "Gemini API quota or rate limit reached; check AI Studio limits.",
                        503,
                    ),
                }
                if response.status_code in errors:
                    raise LLMError(*errors[response.status_code])
                if response.status_code != 200:
                    raise LLMError("llm_provider_error", "Gemini returned an error.")
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise LLMError("llm_invalid_output", "Unexpected Gemini response encoding.")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > 256_000:
                        raise LLMError(
                            "llm_invalid_output", "Gemini response exceeds the size limit."
                        )
                    body.extend(chunk)
        try:
            data = json.loads(body)
            if not isinstance(data, dict):
                raise ValueError
            return data
        except (ValueError, UnicodeError) as exc:
            raise LLMError("llm_invalid_output", "Gemini returned invalid JSON.") from exc
