"""OAuth 2.0 authorization code flow endpoints."""

from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from vertical_api.client import MissingCredentialsError
from vertical_impl.oauth import auth_callback as oauth_auth_callback
from vertical_impl.oauth import build_authorization_url
from vertical_impl.token_store import store_token

from vertical_service.sessions import OAUTH_SESSION_ID_KEY

router = APIRouter()

_SUCCESS_REDIRECT_ENV = "OAUTH_SUCCESS_REDIRECT"


@router.get("/login")
def auth_login(request: Request) -> RedirectResponse:
    """Start OAuth: ensure a session id, then redirect the browser to the provider."""
    if OAUTH_SESSION_ID_KEY not in request.session:
        request.session[OAUTH_SESSION_ID_KEY] = str(uuid4())
    session_id = request.session[OAUTH_SESSION_ID_KEY]
    try:
        authorization_url = build_authorization_url(session_id)
    except MissingCredentialsError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return RedirectResponse(
        url=authorization_url,
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/callback")
def auth_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Handle the provider redirect: exchange the code and persist tokens for this session."""
    session_id = request.session.get(OAUTH_SESSION_ID_KEY, "")
    result = oauth_auth_callback(session_id, code, state, provider_error=error)
    if not result.success:
        status_code = status.HTTP_502_BAD_GATEWAY if result.error_type == "exchange_error" else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code, detail=result.error or "OAuth callback failed.")

    if not session_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Missing OAuth session.",
        )
    if result.token_data is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OAuth succeeded without token data.",
        )

    store_token(session_id, result.token_data)
    destination = os.environ.get(_SUCCESS_REDIRECT_ENV, "/docs")
    return RedirectResponse(url=destination, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
