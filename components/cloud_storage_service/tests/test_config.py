"""Tests for service configuration."""

from __future__ import annotations

import pytest
from cloud_storage_service.app import create_app

pytestmark = pytest.mark.unit


def test_create_app_requires_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without SESSION_SECRET_KEY, the app cannot start (sessions are required for OAuth)."""
    monkeypatch.delenv("SESSION_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="SESSION_SECRET_KEY"):
        create_app()
