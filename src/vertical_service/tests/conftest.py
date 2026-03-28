"""Shared fixtures for vertical_service tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _session_secret_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Session middleware requires a secret; use a stable value in tests."""
    monkeypatch.setenv(
        "SESSION_SECRET_KEY",
        "test-session-secret-key-at-least-32-bytes-long",
    )


@pytest.fixture
def oauth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minimal OAuth-related environment for login redirect tests."""
    monkeypatch.setenv("OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("OAUTH_AUTH_URL", "https://idp.example/oauth/authorize")
    monkeypatch.setenv("OAUTH_TOKEN_URL", "https://idp.example/oauth/token")
    monkeypatch.setenv("OAUTH_REDIRECT_URI", "http://127.0.0.1:8000/auth/callback")
