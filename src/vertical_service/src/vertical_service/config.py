"""Service configuration loaded from the environment."""

from __future__ import annotations

import os


def session_secret_key() -> str:
    """Return the secret used to sign session cookies (required in every environment)."""
    key = os.environ.get("SESSION_SECRET_KEY")
    if not key:
        msg = "SESSION_SECRET_KEY must be set for signed browser sessions (OAuth flow)."
        raise RuntimeError(msg)
    return key
