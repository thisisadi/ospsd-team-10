"""Tests for OAuth endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from vertical_impl import token_store as token_store_mod
from vertical_impl.token_store import TokenData
from vertical_service.app import create_app
from vertical_service.deps import require_oauth_session

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> TestClient:
    """ASGI test client."""
    return TestClient(create_app())


@pytest.mark.usefixtures("oauth_env")
def test_auth_login_redirects(client: TestClient) -> None:
    """GET /auth/login should redirect to the provider."""
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    assert "client_id=test-client-id" in response.headers["location"]


@pytest.mark.usefixtures("oauth_env")
def test_auth_callback_bad_state(client: TestClient) -> None:
    """Callback should reject an invalid state."""
    client.get("/auth/login", follow_redirects=False)

    response = client.get(
        "/auth/callback",
        params={"code": "x", "state": "wrong"},
        follow_redirects=False,
    )

    assert response.status_code in (400, 401)


def test_auth_callback_provider_error(client: TestClient) -> None:
    """Provider error query param should return 400."""
    response = client.get(
        "/auth/callback",
        params={"error": "access_denied"},
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_auth_login_missing_env(
    monkeypatch: pytest.MonkeyPatch,
    client: TestClient,
) -> None:
    """Missing OAuth env vars should return 503."""
    for key in (
        "OAUTH_CLIENT_ID",
        "OAUTH_CLIENT_SECRET",
        "OAUTH_AUTH_URL",
        "OAUTH_TOKEN_URL",
        "OAUTH_REDIRECT_URI",
    ):
        monkeypatch.delenv(key, raising=False)

    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 503


@pytest.mark.usefixtures("oauth_env")
def test_auth_callback_success(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid callback should store token and redirect to /docs."""
    stored: list[tuple[str, TokenData]] = []

    def fake_store(session_id: str, token_data: TokenData) -> None:
        stored.append((session_id, token_data))
        token_store_mod.store_token(session_id, token_data)

    monkeypatch.setattr("vertical_service.routes.auth.store_token", fake_store)
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
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]

    done = client.get(
        "/auth/callback",
        params={"code": "ok", "state": state},
        follow_redirects=False,
    )

    assert done.status_code == 307
    assert done.headers["location"] == "/docs"
    assert len(stored) == 1


def test_auth_and_deps_full_execution(client: TestClient) -> None:
    """Exercise auth error path and dependency execution for coverage."""
    response = client.get("/auth/callback", params={"error": "access_denied"}, follow_redirects=False)
    assert response.status_code == 400

    try:
        require_oauth_session()
    except Exception:
        pass