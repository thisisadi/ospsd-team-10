"""Tests for dependency helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from vertical_impl.token_store import TokenData, store_token
from vertical_service.deps import require_oauth_session
from vertical_service.sessions import OAUTH_SESSION_ID_KEY


class _DummyRequest:
    def __init__(self, session: dict) -> None:
        self.session = session


def test_require_oauth_session_raises_when_missing() -> None:
    request = _DummyRequest({})
    with pytest.raises(HTTPException) as exc:
        require_oauth_session(request)
    assert exc.value.status_code == 401


def test_require_oauth_session_returns_session_id() -> None:
    session_id = "abc123"

    store_token(
        session_id,
        TokenData(
            access_token="token",  # noqa: S106
            token_type="Bearer",  # noqa: S106
            expires_at=None,
        ),
    )

    request = _DummyRequest({OAUTH_SESSION_ID_KEY: session_id})

    assert require_oauth_session(request) == session_id
