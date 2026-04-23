"""FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request, status
from vertical_impl.token_store import get_token

from vertical_service.sessions import OAUTH_SESSION_ID_KEY


def require_oauth_session(request: Request) -> str:
    """Require a browser session that has completed OAuth (token stored for this session id)."""
    raw = request.session.get(OAUTH_SESSION_ID_KEY)
    if not isinstance(raw, str) or get_token(raw) is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Visit /auth/login first.",
        )
    return raw