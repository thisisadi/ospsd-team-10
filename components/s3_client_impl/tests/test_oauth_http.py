"""Unit tests for OAuth HTTP helpers (mocked requests)."""

from __future__ import annotations

from datetime import UTC
from unittest.mock import MagicMock

import pytest
import requests
from s3_client_impl.oauth import exchange_code_for_token, refresh_access_token
from s3_client_impl.token_store import TokenData

pytestmark = pytest.mark.unit


@pytest.fixture
def oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimal OAuth env for token URL calls."""
    monkeypatch.setenv("OAUTH_CLIENT_ID", "cid")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "sec")
    monkeypatch.setenv("OAUTH_AUTH_URL", "https://example/oauth/authorize")
    monkeypatch.setenv("OAUTH_TOKEN_URL", "https://example/oauth/token")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://localhost:8000/cb")


def _ok_json(payload: dict[str, object]) -> MagicMock:
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.mark.usefixtures("oauth_env")
def test_exchange_code_for_token_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """exchange_code_for_token posts to the token endpoint and maps JSON to TokenData."""
    calls: list[dict[str, object]] = []

    def _fake_post(url: str, **_kwargs: object) -> MagicMock:
        calls.append({"url": url})
        return _ok_json(
            {
                "access_token": "access",
                "token_type": "Bearer",
                "expires_in": 3600,
                "refresh_token": "refresh",
                "scope": "read",
            },
        )

    monkeypatch.setattr("s3_client_impl.oauth.requests.post", _fake_post)
    token = exchange_code_for_token("auth-code")
    assert isinstance(token, TokenData)
    assert token.access_token == "access"  # noqa: S105
    assert token.refresh_token == "refresh"  # noqa: S105
    assert token.scope == "read"
    assert token.expires_at is not None
    assert len(calls) >= 1
    assert calls[0]["url"] == "https://example/oauth/token"


@pytest.mark.usefixtures("oauth_env")
def test_exchange_code_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provider errors should surface as requests.HTTPError."""

    def _fake_post(*_args: object, **_kwargs: object) -> MagicMock:
        response = MagicMock()
        response.raise_for_status.side_effect = requests.HTTPError("bad token")
        return response

    monkeypatch.setattr("s3_client_impl.oauth.requests.post", _fake_post)
    with pytest.raises(requests.HTTPError):
        exchange_code_for_token("bad")


@pytest.mark.usefixtures("oauth_env")
def test_refresh_access_token_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh_access_token uses grant_type=refresh_token."""
    monkeypatch.setattr(
        "s3_client_impl.oauth.requests.post",
        lambda *_a, **_k: _ok_json(
            {
                "access_token": "new-access",
                "token_type": "Bearer",
                "expires_in": 60,
                "refresh_token": "still-refresh",
                "scope": "s",
            },
        ),
    )
    token = refresh_access_token("old-refresh")
    assert token.access_token == "new-access"  # noqa: S105
    assert token.refresh_token == "still-refresh"  # noqa: S105
    assert token.expires_at is not None
    assert token.expires_at.tzinfo == UTC
