"""HTTP implementation of Shared-API :class:`chat_client_api.client.ChatClient` (Team 9 OpenAPI)."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from http import HTTPStatus
from typing import TYPE_CHECKING

import httpx
from chat_client_api.client import (
    Channel,
    ChannelNotFoundError,
    ChatClient,
    ChatError,
    Message,
    MessageDeleteError,
    MessageNotFoundError,
)
from chat_client_service_api_client.api.default import (
    get_messages_messages_get,
    list_channels_channels_get,
)
from chat_client_service_api_client.client import Client as OpenApiClient
from chat_client_service_api_client.models.get_messages_response import GetMessagesResponse
from chat_client_service_api_client.models.http_validation_error import HTTPValidationError
from chat_client_service_api_client.models.list_channels_response import ListChannelsResponse

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

if TYPE_CHECKING:
    from chat_client_service_api_client.models.message_model import MessageModel


def _slack_ts_to_datetime(ts: str) -> datetime:
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (ValueError, OSError):
        return datetime.now(tz=UTC)


def _read_required_env() -> tuple[str, str]:
    """Return (base_url, session_id) or raise ValueError if missing."""
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
    if isinstance(parsed, HTTPValidationError):
        return f"{MSG_VALIDATION} Details: {parsed.to_dict()}"
    return MSG_VALIDATION


def _safe_preview_bytes(data: bytes, limit: int = 512) -> str:
    text = data.decode("utf-8", errors="replace")
    if len(text) > limit:
        return f"{text[:limit]}…"
    return text


def _extract_message_id_from_bytes(data: bytes) -> str | None:
    try:
        payload = json.loads(data.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    raw_id = payload.get("message_id")
    if isinstance(raw_id, str) and raw_id:
        return raw_id
    return None


def _parse_send_payload(data: bytes) -> dict[str, object]:
    try:
        raw = json.loads(data.decode("utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}
    return raw if isinstance(raw, dict) else {}


class HttpChatClient(ChatClient):
    """HTTP client for Team 9 chat (Slack) using the generated OpenAPI client."""

    def __init__(self) -> None:
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

    def send_message(self, channel_id: str, text: str) -> Message:
        base_url, session_id = _read_required_env()
        client = self._ensure_api(base_url)

        try:
            response = client.get_httpx_client().request(
                method="post",
                url="/messages",
                headers={"Content-Type": "application/json", "X-Session-ID": session_id},
                json={"channel": channel_id, "text": text},
            )
        except httpx.RequestError as exc:
            raise ChatError(f"{MSG_NETWORK} ({type(exc).__name__}).") from exc

        status_code = int(response.status_code)
        if _is_auth_rejection(status_code):
            raise ChatError(MSG_AUTH_SESSION)

        if status_code == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ChatError(MSG_VALIDATION)

        if status_code != HTTPStatus.OK:
            body_preview = _safe_preview_bytes(response.content)
            msg = f"{MSG_UNEXPECTED_SEND} (status={status_code}; body={body_preview!s})."
            raise ChatError(msg)

        parsed_message_id = _extract_message_id_from_bytes(response.content)
        if parsed_message_id is None:
            raise ChatError(MSG_NO_MESSAGE_ID)

        payload = _parse_send_payload(response.content)
        ch_val = payload.get("channel")
        ch: str = ch_val if isinstance(ch_val, str) else channel_id
        text_val = payload.get("text")
        body_text: str = text_val if isinstance(text_val, str) else text
        sender_val = payload.get("sender")
        sender: str = sender_val if isinstance(sender_val, str) else "agent"
        ts_raw = payload.get("timestamp")
        ts = _slack_ts_to_datetime(ts_raw) if isinstance(ts_raw, str) and ts_raw else datetime.now(tz=UTC)

        return Message(
            message_id=parsed_message_id,
            channel=ch,
            text=body_text,
            sender=sender,
            timestamp=ts,
        )

    def get_channels(self) -> list[Channel]:
        base_url, session_id = _read_required_env()
        client = self._ensure_api(base_url)

        try:
            detailed = list_channels_channels_get.sync_detailed(
                client=client,
                x_session_id=session_id,
            )
        except httpx.RequestError as exc:
            raise ChatError(f"{MSG_NETWORK} ({type(exc).__name__}).") from exc

        if _is_auth_rejection(int(detailed.status_code)):
            raise ChatError(MSG_AUTH_SESSION)

        if int(detailed.status_code) == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ChatError(_validation_error_message(parsed=detailed.parsed))

        if int(detailed.status_code) != HTTPStatus.OK or detailed.parsed is None:
            body_preview = _safe_preview_bytes(detailed.content)
            raise ChatError(
                f"Unexpected Team 9 list_channels response (status={int(detailed.status_code)}; body={body_preview!s}).",
            )

        if not isinstance(detailed.parsed, ListChannelsResponse):
            raise ChatError("Team 9 list_channels response payload was not understood.")

        return [
            Channel(
                channel_id=item.channel_id,
                name=item.name,
                is_private=item.is_private,
                channel_type="private" if item.is_private else "public",
            )
            for item in detailed.parsed.channels
        ]

    def get_channel(self, channel_id: str) -> Channel:
        for ch in self.get_channels():
            if ch.channel_id == channel_id:
                return ch
        raise ChannelNotFoundError(f"No channel found for id {channel_id!r}.")

    def get_messages(
        self,
        channel_id: str,
        limit: int = 10,
        cursor: str | None = None,
    ) -> list[Message]:
        base_url, session_id = _read_required_env()
        client = self._ensure_api(base_url)

        try:
            detailed = get_messages_messages_get.sync_detailed(
                client=client,
                channel=channel_id,
                limit=limit,
                cursor=cursor,
                x_session_id=session_id,
            )
        except httpx.RequestError as exc:
            raise ChatError(f"{MSG_NETWORK} ({type(exc).__name__}).") from exc

        if _is_auth_rejection(int(detailed.status_code)):
            raise ChatError(MSG_AUTH_SESSION)

        if int(detailed.status_code) == HTTPStatus.UNPROCESSABLE_ENTITY:
            raise ChatError(_validation_error_message(parsed=detailed.parsed))

        if detailed.status_code != HTTPStatus.OK or detailed.parsed is None:
            body_preview = _safe_preview_bytes(detailed.content)
            msg = f"Unexpected Team 9 get_messages response (status={int(detailed.status_code)}; body={body_preview!s})."
            raise ChatError(msg)

        if not isinstance(detailed.parsed, GetMessagesResponse):
            raise ChatError("Team 9 get_messages response payload was not understood.")

        return [_to_message(item) for item in detailed.parsed.messages]

    def get_message(self, message_id: str) -> Message:
        if ":" in message_id:
            head, _tail = message_id.split(":", 1)
            for msg in self.get_messages(head, limit=500):
                if msg.message_id == message_id:
                    return msg
        else:
            for ch in self.get_channels():
                for msg in self.get_messages(ch.channel_id, limit=500):
                    if msg.message_id == message_id:
                        return msg
        raise MessageNotFoundError(f"No message found for id {message_id!r}.")

    def delete_message(self, _message_id: str) -> None:
        raise MessageDeleteError("Team 9 chat API does not expose message delete.")


def _to_message(model: MessageModel) -> Message:
    return Message(
        message_id=model.message_id,
        channel=model.channel,
        text=model.text,
        sender=model.sender,
        timestamp=_slack_ts_to_datetime(model.timestamp),
    )
