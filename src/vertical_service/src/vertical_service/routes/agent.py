"""POST /agent — Slack (or other chat) bot integration entrypoint."""

from __future__ import annotations

from typing import Annotated, Any

from cloud_storage_api import CloudStorageClient
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from chat_client_api import ChatServiceError, send_agent_response
from openai_ai_client_impl import OpenAIAIClient
from vertical_service.agent import default_storage_container, run_agent_turn
from vertical_service.deps import verify_api_key

router = APIRouter()


class AgentRequest(BaseModel):
    """Inbound payload from the chat integration layer."""

    message: str = Field(..., min_length=1, description="End-user or bot-composed instruction text.")
    channel_id: str | None = Field(default=None, description="Chat channel; echoed back for downstream send_message.")
    container: str | None = Field(default=None, description="Optional storage container (S3 bucket) override.")
    context: dict[str, Any] | None = Field(default=None, description="Extra structured context from the chat platform.")


class AgentResponse(BaseModel):
    """JSON returned to the chat integration for posting back to the user."""

    reply: str
    channel_id: str | None = None
    sent_message_id: str | None = None


def _get_openai_client(request: Request) -> OpenAIAIClient:
    raw = getattr(request.app.state, "ai_client", None)
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI client is not configured (set OPENAI_API_KEY).",
        )
    if not isinstance(raw, OpenAIAIClient):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configured AI client does not support agent tools.",
        )
    return raw


def _get_storage(request: Request) -> CloudStorageClient:
    client: CloudStorageClient = request.app.state.storage_client
    return client


@router.post("/agent", response_model=AgentResponse)
def agent_endpoint(
    body: AgentRequest,
    _verified: Annotated[str, Depends(verify_api_key)],
    storage: Annotated[CloudStorageClient, Depends(_get_storage)],
    ai: Annotated[OpenAIAIClient, Depends(_get_openai_client)],
) -> AgentResponse:
    """Run prompt/action routing and tool-assisted completion; return text for the chat layer."""
    try:
        container = default_storage_container(body.container)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    ctx = dict(body.context or {})
    if body.channel_id:
        ctx.setdefault("channel_id", body.channel_id)

    reply = run_agent_turn(
        message=body.message,
        storage=storage,
        ai=ai,
        container=container,
        request_context=ctx,
    )
    sent_message_id: str | None = None
    if body.channel_id:
        try:
            sent_message_id = send_agent_response(body.channel_id, reply)
        except ChatServiceError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc

    return AgentResponse(
        reply=reply,
        channel_id=body.channel_id,
        sent_message_id=sent_message_id,
    )
