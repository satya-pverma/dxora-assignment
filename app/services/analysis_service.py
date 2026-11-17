import time

from app.schemas import AnalysisMetadata, LinkAnalysisResponse
from app.services.llm_service import LLMError, LLMService
from app.services.website_extractor import WebsiteExtractor


class AnalysisService:
    def __init__(self, extractor: WebsiteExtractor, llm: LLMService) -> None:
        self.extractor = extractor
        self.llm = llm

    async def analyze(self, url: str) -> LinkAnalysisResponse:
        # Missing credentials should not trigger a website fetch.
        self.llm.require_credentials()
        started = time.perf_counter()
        website = await self.extractor.extract(url)
        result, usage = await self.llm.analyze(website)
        for service in result.analysis.top_services:
            if service.evidence_type == "observed" and service.source_quote not in website.text:
                raise LLMError(
                    "llm_unsupported_claim",
                    "A service quote was not found in the website evidence.",
                )
        warnings = [
            "Competitors are unverified AI suggestions; independent research was not performed.",
            "SEO and audience insights are recommendations, not measured search or market data.",
        ]
        if website.truncated:
            warnings.append("Website text was truncated before analysis.")
        if any(s.evidence_type == "inferred_recommendation" for s in result.analysis.top_services):
            warnings.append("Some service entries are proposed offerings, not observed services.")
        if len(result.analysis.competitor_analysis.competitors) < 3:
            warnings.append("Fewer than three competitor suggestions were available.")
        return LinkAnalysisResponse(
            **result.model_dump(),
            website=website.requested_url,
            metadata=AnalysisMetadata(
                provider="openai",
                model=self.llm.settings.llm_model,
                source_url=website.final_url,
                content_truncated=website.truncated,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                elapsed_seconds=round(time.perf_counter() - started, 3),
                warnings=warnings,
            ),
        )
