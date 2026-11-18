from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app, get_settings, require_demo_access


def test_dashboard_and_assets():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        for asset in ("/static/app.js", "/static/style.css"):
            assert client.get(asset).status_code == 200
        assert client.get("/static/../config.py").status_code == 404


def test_forms_offer_both_flows_and_explicit_publication_confirmation():
    page = BeautifulSoup(Path("app/static/index.html").read_text(encoding="utf-8"), "html.parser")
    assert page.select_one("#analysis-form input[type=url][required]")
    assert page.select_one("#posting-form textarea[required]")
    assert page.select_one("#confirm-publish[type=checkbox][required]")
    assert page.select_one("#demo-key[type=password]")
    assert len(page.select("[role=status]")) == 2


def test_access_key_comparison(monkeypatch):
    monkeypatch.setattr(
        "app.main.get_settings", lambda: Settings(_env_file=None, demo_access_key="private-demo")
    )
    require_demo_access("private-demo")
    for key in (None, "wrong", "non-ascii-\u2603"):
        with pytest.raises(HTTPException) as error:
            require_demo_access(key)
        assert error.value.status_code == 401


def test_public_health_and_protected_actions():
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    # The guard calls get_settings directly, so patch it independently of service dependencies.
    from unittest.mock import patch

    try:
        with patch(
            "app.main.get_settings",
            return_value=Settings(_env_file=None, demo_access_key="private-demo"),
        ):
            with TestClient(app) as client:
                assert client.get("/health").status_code == 200
                assert client.get("/").status_code == 200
                assert (
                    client.post("/link-analysis", json={"url": "https://example.com"}).status_code
                    == 401
                )
                assert (
                    client.post("/posting", json={"message": "Hi https://example.com"}).status_code
                    == 401
                )
    finally:
        app.dependency_overrides.clear()
