"""FastAPI dependency for service-to-service ``X-API-Key`` validation on ``/agent``."""

from __future__ import annotations

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from vertical_service.agent_api import (
    ENV_AGENT_API_KEY,
    HTTP_HEADER_X_API_KEY,
    MSG_INVALID_OR_MISSING_KEY,
    MSG_SERVER_AGENT_KEY_UNSET,
)


def verify_api_key(
    x_api_key: Annotated[str | None, Header(alias=HTTP_HEADER_X_API_KEY)] = None,
) -> str:
    """Validate the ``X-API-Key`` header against :envvar:`AGENT_API_KEY` for service-to-service calls to ``/agent``."""
    expected_raw = os.environ.get(ENV_AGENT_API_KEY, "")
    expected = expected_raw.strip()
    if not expected:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=MSG_SERVER_AGENT_KEY_UNSET,
        )
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail=MSG_INVALID_OR_MISSING_KEY,
        )
    return x_api_key
