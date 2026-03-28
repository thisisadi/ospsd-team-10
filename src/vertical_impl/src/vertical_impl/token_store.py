"""Simple in-memory token store for OAuth sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class TokenData:
    """Stored OAuth token information for one user/session."""

    access_token: str
    token_type: str
    expires_at: datetime | None
    refresh_token: str | None = None
    scope: str | None = None


_TOKEN_STORE: dict[str, TokenData] = {}


def store_token(session_id: str, token_data: TokenData) -> None:
    """Store token data for a session."""
    _TOKEN_STORE[session_id] = token_data


def get_token(session_id: str) -> TokenData | None:
    """Return token data for a session if present."""
    return _TOKEN_STORE.get(session_id)


def delete_token(session_id: str) -> None:
    """Remove token data for a session."""
    _TOKEN_STORE.pop(session_id, None)


def is_token_expired(token_data: TokenData, skew_seconds: int = 30) -> bool:
    """Return True if token is expired or about to expire."""
    if token_data.expires_at is None:
        return False
    return datetime.now(UTC) >= token_data.expires_at - timedelta(seconds=skew_seconds)
