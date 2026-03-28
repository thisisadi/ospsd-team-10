"""Tests for OAuth endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from vertical_impl.token_store import TokenData
from vertical_service.app import create_app

from vertical_impl import token_store as token_store_mod

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> TestClient:
    """ASGI test client with session support."""
    return TestClient(create_app())


@pytest.mark.usefixtures("oauth_env")
def test_auth_login_redirects_to_provider(client: TestClient) -> None:
    """GET /auth/login should redirect to the configured authorization URL."""
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert location.startswith("https://idp.example/oauth/authorize?")
    assert "client_id=test-client-id" in location
    assert "state=" in location


@pytest.mark.usefixtures("oauth_env")
def test_auth_callback_rejects_bad_state(client: TestClient) -> None:
    """Callback must reject a state that does not match the session."""
    client.get("/auth/login", follow_redirects=False)
    response = client.get(
        "/auth/callback",
        params={"code": "fake-code", "state": "not-the-right-state"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()


def test_auth_callback_propagates_provider_error(client: TestClient) -> None:
    """OAuth error query param should surface as a 400."""
    response = client.get("/auth/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert response.status_code == 400
    assert "access_denied" in response.json()["detail"]


def test_auth_login_without_oauth_config_returns_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """If OAuth env vars are missing, /auth/login should not redirect."""
    for name in (
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "OAUTH_AUTH_URL",
        "OAUTH_TOKEN_URL",
        "OAUTH_REDIRECT_URI",
    ):
        monkeypatch.delenv(name, raising=False)
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 503


@pytest.mark.usefixtures("oauth_env")
def test_auth_callback_success_stores_token_and_redirects(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: valid state, mocked token exchange, token stored for session."""
    stored: list[tuple[str, TokenData]] = []

    def _spy_store(session_id: str, token_data: TokenData) -> None:
        stored.append((session_id, token_data))
        token_store_mod.store_token(session_id, token_data)

    monkeypatch.setattr("vertical_service.routes.auth.store_token", _spy_store)
    monkeypatch.setattr(
        "vertical_impl.oauth.exchange_code_for_token",
        lambda _code: TokenData(
            access_token="at",  # noqa: S106
            token_type="Bearer",  # noqa: S106
            expires_at=datetime.now(UTC),
            refresh_token="rt",  # noqa: S106
            scope="s",
        ),
    )
    start = client.get("/auth/login", follow_redirects=False)
    assert start.status_code == 307
    location = start.headers["location"]
    state = parse_qs(urlparse(location).query)["state"][0]
    done = client.get("/auth/callback", params={"code": "auth-code", "state": state}, follow_redirects=False)
    assert done.status_code == 307
    assert done.headers["location"] == "/docs"
    assert len(stored) == 1
    assert stored[0][1].access_token == "at"  # noqa: S105
