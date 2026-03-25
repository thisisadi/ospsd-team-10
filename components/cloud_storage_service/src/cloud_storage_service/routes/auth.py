"""OAuth 2.0 authorization code flow endpoints."""

from __future__ import annotations

import os
from uuid import uuid4

import requests
from cloud_storage_client_api.client import MissingCredentialsError
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from s3_client_impl.oauth import build_authorization_url, exchange_code_for_token, validate_state
from s3_client_impl.token_store import store_token

from cloud_storage_service.sessions import OAUTH_SESSION_ID_KEY

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
    if error:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth provider error: {error}",
        )
    if not code or not state:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Missing authorization code or state.",
        )
    session_id = request.session.get(OAUTH_SESSION_ID_KEY)
    if not session_id or not validate_state(session_id, state):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired OAuth state.",
        )
    try:
        token_data = exchange_code_for_token(code)
    except MissingCredentialsError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except requests.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Token exchange with the provider failed.",
        ) from exc

    store_token(session_id, token_data)
    destination = os.environ.get(_SUCCESS_REDIRECT_ENV, "/docs")
    return RedirectResponse(url=destination, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
