"""HTTP implementation of :class:`chat_client_api.ChatClient` using the Team 9 OpenAPI client."""

from __future__ import annotations

import os
from http import HTTPStatus

import httpx
from chat_client_service_api_client.api.default import health_health_get, send_message_messages_post
from chat_client_service_api_client.client import Client as OpenApiClient
from chat_client_service_api_client.models.http_validation_error import HTTPValidationError
from chat_client_service_api_client.models.send_message_request import SendMessageRequest
from chat_client_service_api_client.models.send_message_response_model import SendMessageResponseModel

from chat_client_api import (
    ChatClient,
    ChatServiceAuthError,
    ChatServiceError,
    register_client,
)
from http_chat_client_impl._config import (
    ENV_CHAT_SERVICE_BASE_URL,
    ENV_CHAT_SESSION_ID,
    MSG_AUTH_SESSION,
    MSG_MISSING_BASE,
    MSG_MISSING_SESSION,
    MSG_NETWORK,
    MSG_NO_MESSAGE_ID,
    MSG_UNEXPECTED_SEND,
    MSG_VALIDATION,
)


def _read_required_env() -> tuple[str, str]:
    """Return (base_url, session_id) or raise :class:`ValueError` for missing/blank configuration."""
    base_raw = os.environ.get(ENV_CHAT_SERVICE_BASE_URL, "")
    session_raw = os.environ.get(ENV_CHAT_SESSION_ID, "")
    base = base_raw.strip()
    session = session_raw.strip()
    if not base:
        raise ValueError(MSG_MISSING_BASE)
    if not session:
        raise ValueError(MSG_MISSING_SESSION)
    return base, session


def _is_auth_rejection(status_code: int) -> bool:
    return status_code in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)


def _validation_error_message(*, parsed: object | None) -> str:
    """Build a user-facing string for a 422 body from the OpenAPI client, if available."""
    if isinstance(parsed, HTTPValidationError):
        return f"{MSG_VALIDATION} Details: {parsed.to_dict()}"
    return MSG_VALIDATION


class HttpChatClient(ChatClient):
    """Synchronous client that talks to Team 9's FastAPI service via the generated httpx client."""

    def __init__(self) -> None:
        """Create a client. Remote configuration is read from the environment for each public call."""
        self._api_client: OpenApiClient | None = None
        self._api_base: str = ""

    def _ensure_api(self, base_url: str) -> OpenApiClient:
        if self._api_client is None or self._api_base != base_url:
            self._api_base = base_url
            self._api_client = OpenApiClient(
                base_url=base_url,
                raise_on_unexpected_status=False,
            )
        return self._api_client

    def send_message(self, channel: str, text: str) -> str:
        """Post ``text`` to ``channel`` and return the remote ``message_id`` string."""
        base_url, session_id = _read_required_env()
        client = self._ensure_api(base_url)
        try:
            detailed = send_message_messages_post.sync_detailed(
                client=client,
                body=SendMessageRequest(
                    channel=channel,
                    text=text,
                ),
                x_session_id=session_id,
            )
        except httpx.RequestError as exc:
            network_detail = f"{MSG_NETWORK} ({type(exc).__name__})."
            raise ChatServiceError(network_detail) from exc
        if _is_auth_rejection(int(detailed.status_code)):
            raise ChatServiceAuthError(MSG_AUTH_SESSION)
        if int(detailed.status_code) == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ChatServiceError(
                _validation_error_message(parsed=detailed.parsed),
                status_code=int(HTTPStatus.UNPROCESSABLE_ENTITY),
            )
        if detailed.status_code != HTTPStatus.OK or detailed.parsed is None:
            body_preview = _safe_preview_bytes(detailed.content)
            msg = f"{MSG_UNEXPECTED_SEND} (status={int(detailed.status_code)}; body={body_preview!s})."
            raise ChatServiceError(msg, status_code=int(detailed.status_code))
        if isinstance(detailed.parsed, SendMessageResponseModel) and detailed.parsed.message_id:
            return str(detailed.parsed.message_id)
        raise ChatServiceError(MSG_NO_MESSAGE_ID, status_code=int(detailed.status_code))

    def check_health(self) -> bool:
        """Call ``GET /health`` and return whether the call succeeded and parsed a payload."""
        base_url, _session_id = _read_required_env()
        client = self._ensure_api(base_url)
        try:
            detailed = health_health_get.sync_detailed(client=client)
        except httpx.RequestError:
            return False
        return int(detailed.status_code) == HTTPStatus.OK and detailed.parsed is not None


def _safe_preview_bytes(data: bytes, limit: int = 512) -> str:
    text = data.decode("utf-8", errors="replace")
    if len(text) > limit:
        return f"{text[:limit]}…"
    return text


def _register_default() -> None:
    register_client(HttpChatClient())


_register_default()
