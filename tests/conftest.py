import pytest

from app.main import analysis_rate_limiter


@pytest.fixture(autouse=True)
def reset_analysis_rate_limit():
    analysis_rate_limiter.clear()
    yield
    analysis_rate_limiter.clear()
