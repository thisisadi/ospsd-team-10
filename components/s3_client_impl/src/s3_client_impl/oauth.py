"""OAuth 2.0 Authorization Code Flow helpers."""

from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

import requests
from cloud_storage_client_api.client import MissingCredentialsError
from dotenv import load_dotenv

from s3_client_impl.token_store import TokenData

# Load environment variables from .env
load_dotenv()


_MISSING_ENV_MSG = "Missing required OAuth environment variable: {name}"


@dataclass(frozen=True)
class OAuthConfig:
    """Configuration for OAuth 2.0 Authorization Code Flow."""

    client_id: str
    client_secret: str
    auth_url: str
    token_url: str
    redirect_uri: str
    scope: str


_STATE_STORE: dict[str, str] = {}


def _require_env(name: str) -> str:
    """Get required environment variable or raise error."""
    value = os.environ.get(name)
    if not value:
        raise MissingCredentialsError(_MISSING_ENV_MSG.format(name=name))
    return value


def load_oauth_config_from_env() -> OAuthConfig:
    """Load OAuth config from environment variables."""
    return OAuthConfig(
        client_id=_require_env("OAUTH_CLIENT_ID"),
        client_secret=_require_env("OAUTH_CLIENT_SECRET"),
        auth_url=_require_env("OAUTH_AUTH_URL"),
        token_url=_require_env("OAUTH_TOKEN_URL"),
        redirect_uri=_require_env("OAUTH_REDIRECT_URI"),
        scope=os.environ.get("OAUTH_SCOPE", ""),
    )


def create_state(session_id: str) -> str:
    """Create and store a CSRF protection state value."""
    state = secrets.token_urlsafe(32)
    _STATE_STORE[session_id] = state
    return state


def validate_state(session_id: str, state: str) -> bool:
    """Validate returned OAuth state."""
    expected = _STATE_STORE.get(session_id)
    return expected is not None and secrets.compare_digest(expected, state)


def build_authorization_url(session_id: str) -> str:
    """Generate OAuth authorization URL."""
    config = load_oauth_config_from_env()
    state = create_state(session_id)

    params = {
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "state": state,
    }

    if config.scope:
        params["scope"] = config.scope

    return f"{config.auth_url}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> TokenData:
    """Exchange authorization code for access token."""
    config = load_oauth_config_from_env()

    response = requests.post(
        config.token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    access_token = payload["access_token"]
    token_type = payload.get("token_type", "Bearer")
    refresh_token = payload.get("refresh_token")
    scope = payload.get("scope")

    expires_in = payload.get("expires_in")
    expires_at = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    return TokenData(
        access_token=access_token,
        token_type=token_type,
        expires_at=expires_at,
        refresh_token=refresh_token,
        scope=scope,
    )


def refresh_access_token(refresh_token: str) -> TokenData:
    """Refresh access token using refresh token."""
    config = load_oauth_config_from_env()

    response = requests.post(
        config.token_url,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
        },
        headers={"Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()

    access_token = payload["access_token"]
    token_type = payload.get("token_type", "Bearer")
    new_refresh_token = payload.get("refresh_token", refresh_token)
    scope = payload.get("scope")

    expires_in = payload.get("expires_in")
    expires_at = None
    if isinstance(expires_in, int):
        expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

    return TokenData(
        access_token=access_token,
        token_type=token_type,
        expires_at=expires_at,
        refresh_token=new_refresh_token,
        scope=scope,
    )
