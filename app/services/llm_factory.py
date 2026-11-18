from app.config import Settings
from app.services.gemini_service import GeminiService
from app.services.llm_service import AnalysisLLM, LLMService


def build_llm_service(settings: Settings) -> AnalysisLLM:
    if settings.llm_provider == "gemini":
        return GeminiService(settings)
    return LLMService(settings)
