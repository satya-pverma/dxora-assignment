import pytest

from app.config import Settings
from app.main import analysis_rate_limiter


@pytest.fixture(autouse=True)
def isolate_local_server_settings(monkeypatch):
    # Endpoint tests must not depend on a developer's .env or personal demo key.
    # Auth-specific tests can replace this fixture's patch with their own settings.
    settings = Settings(_env_file=None, demo_access_key="")
    monkeypatch.setattr("app.main.get_settings", lambda: settings)


@pytest.fixture(autouse=True)
def reset_analysis_rate_limit():
    analysis_rate_limiter.clear()
    yield
    analysis_rate_limiter.clear()
