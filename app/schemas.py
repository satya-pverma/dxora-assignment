"""Public request/response contracts and the model's structured-output schema."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.utils.validators import normalize_website_url

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Platform = Literal["Google", "Facebook", "Instagram", "LinkedIn", "X"]
PLATFORMS = {"Google", "Facebook", "Instagram", "LinkedIn", "X"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LinkAnalysisRequest(StrictModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return str(normalize_website_url(value))


class Brand(StrictModel):
    name: Text
    category: Text
    summary: Text
    products_and_services: list[Text] = Field(max_length=20)


class Competitor(StrictModel):
    name: Text
    evidence_type: Literal["ai_suggestion"]
    rationale: Text
    strengths: list[Text] = Field(max_length=10)
    weaknesses_or_gaps: list[Text] = Field(max_length=10)


class CompetitorAnalysis(StrictModel):
    brand_overview: Text
    competitors: list[Competitor] = Field(max_length=5)
    strengths: list[Text] = Field(max_length=10)
    competitive_advantages: list[Text] = Field(max_length=10)
    opportunities: list[Text] = Field(max_length=10)


class SearchQuery(StrictModel):
    query: Text
    platforms: list[Platform] = Field(min_length=1, max_length=5)
    intent: Text
    business_relevance: Text
    target_audience: Text


class SEOImprovements(StrictModel):
    primary_keyword: Text
    secondary_keywords: list[Text] = Field(max_length=10)
    long_tail_keywords: list[Text] = Field(max_length=10)
    business_keywords: list[Text] = Field(max_length=10)
    recommended_title: Text
    title_rationale: Text
    meta_description: Text
    supporting_content: list[Text] = Field(max_length=10)


class Service(StrictModel):
    name: Text
    description: Text
    target_industry: Text
    target_customer: Text
    main_benefit: Text
    evidence_type: Literal["observed", "inferred_recommendation"]
    source_quote: Text | None

    @model_validator(mode="after")
    def require_observed_evidence(self) -> "Service":
        if self.evidence_type == "observed" and not self.source_quote:
            raise ValueError("Observed services require an exact quote from extracted text.")
        if self.evidence_type == "inferred_recommendation" and self.source_quote is not None:
            raise ValueError("Inferred services must not claim an observed source quote.")
        return self


class TargetAudience(StrictModel):
    primary_audience: list[Text] = Field(max_length=10)
    secondary_audience: list[Text] = Field(max_length=10)
    industries: list[Text] = Field(max_length=10)
    business_types: list[Text] = Field(max_length=10)
    customer_profiles: list[Text] = Field(max_length=10)
    geographical_focus: Text | None
    customer_needs: list[Text] = Field(max_length=10)
    interests: list[Text] = Field(max_length=10)
    marketing_segments: list[Text] = Field(max_length=10)


class Analysis(StrictModel):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: list[SearchQuery] = Field(min_length=5, max_length=5)
    seo_improvements: SEOImprovements
    top_services: list[Service] = Field(min_length=5, max_length=5)
    target_audience: TargetAudience

    @model_validator(mode="after")
    def validate_queries(self) -> "Analysis":
        queries = self.target_search_queries
        if len({query.query.casefold() for query in queries}) != 5:
            raise ValueError("Search queries must be distinct.")
        if {platform for query in queries for platform in query.platforms} != PLATFORMS:
            raise ValueError("Search queries must cover all five supported platforms.")
        return self


class ModelAnalysis(StrictModel):
    brand: Brand
    analysis: Analysis


class AnalysisMetadata(StrictModel):
    provider: Literal["openai"]
    model: str
    source_url: str
    content_truncated: bool
    input_tokens: int | None
    output_tokens: int | None
    elapsed_seconds: float
    warnings: list[str]


class LinkAnalysisResponse(ModelAnalysis):
    success: Literal[True] = True
    website: str
    metadata: AnalysisMetadata


class ErrorDetail(StrictModel):
    code: str
    message: str


class ErrorResponse(StrictModel):
    success: Literal[False] = False
    error: ErrorDetail
