from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.platforms.registry import build_adapters
from app.schemas import (
    ErrorResponse,
    LinkAnalysisRequest,
    LinkAnalysisResponse,
    PostingRequest,
    PostingResponse,
)
from app.services.analysis_service import AnalysisService
from app.services.llm_service import LLMError, LLMService
from app.services.posting_service import PostingService
from app.services.website_extractor import WebsiteExtractor
from app.utils.validators import WebsiteError

app = FastAPI(title=get_settings().app_name)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


def get_analysis_service() -> AnalysisService:
    return AnalysisService(WebsiteExtractor(), LLMService(get_settings()))


@app.exception_handler(LLMError)
async def llm_error_handler(request, exc: LLMError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "error": {"code": exc.code, "message": str(exc)}},
    )


@app.exception_handler(WebsiteError)
async def website_error_handler(request, exc: WebsiteError) -> JSONResponse:
    if exc.code in {"invalid_url", "blocked_destination", "invalid_redirect", "unsafe_redirect"}:
        status_code = 400
    elif exc.code == "website_timeout":
        status_code = 504
    else:
        status_code = 502
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": exc.code, "message": str(exc)}},
    )


@app.post(
    "/link-analysis",
    response_model=LinkAnalysisResponse,
    tags=["analysis"],
    responses={status: {"model": ErrorResponse} for status in (400, 502, 503, 504)},
)
async def link_analysis(
    body: LinkAnalysisRequest,
    service: Annotated[AnalysisService, Depends(get_analysis_service)],
) -> LinkAnalysisResponse:
    return await service.analyze(body.url)


def get_posting_service() -> PostingService:
    settings = get_settings()
    return PostingService(
        build_adapters(settings.posting_platforms), settings.posting_timeout_seconds
    )


@app.post("/posting", response_model=PostingResponse, tags=["posting"])
async def posting(
    body: PostingRequest,
    service: Annotated[PostingService, Depends(get_posting_service)],
) -> PostingResponse:
    return await service.post(body)
