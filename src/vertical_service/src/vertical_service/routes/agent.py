"""POST /agent — poll Team 9 chat, run agent logic, and post a Slack reply."""

from __future__ import annotations

import os
from typing import Annotated, Any, Protocol, cast

from cloud_storage_api import CloudStorageClient
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from chat_client_api import ChatMessage, ChatServiceError, get_client, send_agent_response
from vertical_service.agent import AIClient, default_storage_container, run_agent_turn
from vertical_service.agent_api import (
    ENV_AGENT_API_KEY,
    HTTP_HEADER_X_API_KEY,
    MSG_INVALID_OR_MISSING_KEY,
)

router = APIRouter()


class AgentRequest(BaseModel):
    """Inbound request for one chat polling turn."""

    channel_id: str = Field(..., min_length=1, description="Team 9 / Slack channel id to poll.")
    container: str | None = Field(default=None, description="Optional storage container override.")
    context: dict[str, Any] | None = Field(default=None, description="Extra structured context from the chat platform.")
    limit: int = Field(default=10, ge=1, le=100, description="How many recent messages to inspect from Team 9.")


class AgentResponse(BaseModel):
    """JSON returned after one polling turn."""

    status: str
    channel_id: str
    source_message_id: str | None = None
    source_sender: str | None = None
    source_text: str | None = None
    reply: str | None = None
    sent_message_id: str | None = None


class SupportsAgentAI(Protocol):
    """Minimal protocol for AI clients used by the agent flow."""

    def send_message(self, prompt: str) -> str:
        """Return a text response for a plain prompt."""

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: object,
    ) -> str:
        """Run a tool-enabled chat turn and return the final response."""


def _require_service_key(request: Request) -> None:
    expected = os.environ.get(ENV_AGENT_API_KEY)
    if not expected:
        return
    presented = request.headers.get(HTTP_HEADER_X_API_KEY)
    if presented != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=MSG_INVALID_OR_MISSING_KEY,
        )


def _get_openai_client(request: Request) -> SupportsAgentAI:
    raw = getattr(request.app.state, "ai_client", None)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI client is not configured.",
        )

    if not hasattr(raw, "send_message") or not hasattr(raw, "run_chat_with_tools"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured AI client does not support agent tools.",
        )

    return cast("SupportsAgentAI", raw)


def _get_storage(request: Request) -> CloudStorageClient:
    client: CloudStorageClient = request.app.state.storage_client
    return client


def _processed_message_ids(request: Request) -> set[str]:
    """Return the in-memory set of handled Team 9 message ids."""
    value = getattr(request.app.state, "processed_chat_message_ids", None)
    if value is None:
        value = set()
        request.app.state.processed_chat_message_ids = value
    return cast("set[str]", value)


def _last_processed_timestamps(request: Request) -> dict[str, str]:
    """Return the per-channel last processed message timestamp."""
    value = getattr(request.app.state, "last_processed_chat_timestamps", None)
    if value is None:
        value = {}
        request.app.state.last_processed_chat_timestamps = value
    return cast("dict[str, str]", value)


def _timestamp_key(raw: str) -> tuple[int, str]:
    """Sort Slack-style timestamps safely, falling back to string order."""
    try:
        return (1, f"{float(raw):020.6f}")
    except ValueError:
        return (0, raw)


def _select_message_to_process(
    *,
    messages: list[ChatMessage],
    seen_message_ids: set[str],
    last_processed_timestamp: str | None,
) -> ChatMessage | None:
    """Choose the newest unseen message after the last processed watermark."""
    ordered = sorted(messages, key=lambda item: _timestamp_key(item.timestamp))
    eligible = [
        item
        for item in ordered
        if item.message_id not in seen_message_ids
        and (last_processed_timestamp is None or _timestamp_key(item.timestamp) > _timestamp_key(last_processed_timestamp))
    ]
    if not eligible:
        return None
    return eligible[-1]


@router.post("/agent", response_model=AgentResponse)
def agent_endpoint(
    request: Request,
    body: AgentRequest,
    storage: Annotated[CloudStorageClient, Depends(_get_storage)],
    ai: Annotated[SupportsAgentAI, Depends(_get_openai_client)],
) -> AgentResponse:
    """Poll one channel, process the newest unseen message, and post a reply."""
    _require_service_key(request)
    try:
        container = default_storage_container(body.container)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    try:
        messages = get_client().get_messages(body.channel_id, limit=body.limit)
    except ChatServiceError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    seen_message_ids = _processed_message_ids(request)
    last_processed = _last_processed_timestamps(request)
    selected = _select_message_to_process(
        messages=messages,
        seen_message_ids=seen_message_ids,
        last_processed_timestamp=last_processed.get(body.channel_id),
    )
    if selected is None:
        return AgentResponse(status="idle", channel_id=body.channel_id)

    ctx = dict(body.context or {})
    ctx.setdefault("channel_id", body.channel_id)

    reply = run_agent_turn(
        message=selected.text,
        storage=storage,
        ai=cast("AIClient", ai),
        container=container,
        request_context=ctx,
    )
    try:
        sent_message_id = send_agent_response(body.channel_id, reply)
    except ChatServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    seen_message_ids.add(selected.message_id)
    seen_message_ids.add(sent_message_id)
    last_processed[body.channel_id] = selected.timestamp

    return AgentResponse(
        status="processed",
        channel_id=body.channel_id,
        source_message_id=selected.message_id,
        source_sender=selected.sender,
        source_text=selected.text,
        reply=reply,
        sent_message_id=sent_message_id,
    )
