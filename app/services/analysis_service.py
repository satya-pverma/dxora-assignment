import re
import time

from app.schemas import AnalysisMetadata, LinkAnalysisResponse
from app.services.llm_service import AnalysisLLM
from app.services.website_extractor import WebsiteExtractor


def match_source_quote(quote: str | None, text: str) -> str | None:
    """Match literal words with flexible whitespace, returning the original excerpt."""
    parts = (quote or "").split()
    if not parts:
        return None
    match = re.search(r"\s+".join(re.escape(part) for part in parts), text)
    return match.group() if match else None


class AnalysisService:
    def __init__(self, extractor: WebsiteExtractor, llm: AnalysisLLM) -> None:
        self.extractor = extractor
        self.llm = llm

    async def analyze(self, url: str) -> LinkAnalysisResponse:
        # Missing credentials should not trigger a website fetch.
        self.llm.require_credentials()
        started = time.perf_counter()
        website = await self.extractor.extract(url)
        result, usage = await self.llm.analyze(website)
        for service in result.analysis.top_services:
            if service.evidence_type == "observed":
                matched = match_source_quote(service.source_quote, website.text)
                if matched is None:
                    service.evidence_type = "unverified_ai_output"
                else:
                    service.source_quote = matched
        warnings = [
            "Competitors are unverified AI suggestions; independent research was not performed.",
            "SEO and audience insights are recommendations, not measured search or market data.",
        ]
        if any(s.evidence_type == "unverified_ai_output" for s in result.analysis.top_services):
            warnings.append(
                "Some service claims or quotes could not be matched to the website text; "
                "they are labelled unverified AI output."
            )
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
                provider=self.llm.provider,
                model=self.llm.model,
                source_url=website.final_url,
                content_truncated=website.truncated,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                elapsed_seconds=round(time.perf_counter() - started, 3),
                warnings=warnings,
            ),
        )
