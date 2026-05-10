"""Integration test: live Team 9 chat + in-process /agent with a stub AI client.

Requires ``CHAT_SERVICE_BASE_URL``, ``CHAT_SESSION_ID``, and
``INTEGRATION_AGENT_CHANNEL_ID``. OpenAI is not called; storage uses in-memory mock.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING, Any

import pytest
from chat_client_api import get_client
from fastapi.testclient import TestClient
from vertical_service.app import create_app
from vertical_service.routes.agent import _get_openai_client

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI

pytestmark = [
    pytest.mark.integration,
    pytest.mark.team9_chat,
]

_ENV_NAMES = (
    "CHAT_SERVICE_BASE_URL",
    "CHAT_SESSION_ID",
    "INTEGRATION_AGENT_CHANNEL_ID",
)


def _team9_env_ready() -> bool:
    return all(os.getenv(name, "").strip() for name in _ENV_NAMES)


class _StubAIClient:
    """Minimal AI stand-in: no HTTP to OpenAI; returns a deterministic reply."""

    def send_message(self, prompt: str) -> str:
        return f"stub-send:{prompt[:80]}"

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: object,
    ) -> str:
        del system_prompt, tools, handle_tool
        return f"stub-tools-reply:{user_message}"


@pytest.fixture
def _require_team9_env() -> None:
    if not _team9_env_ready():
        pytest.skip(
            "Set CHAT_SERVICE_BASE_URL, CHAT_SESSION_ID, and INTEGRATION_AGENT_CHANNEL_ID (see README — Team 9 integration)."
        )


@pytest.fixture
def agent_app(
    _require_team9_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[FastAPI, str], None, None]:
    """FastAPI app with mock storage, dummy OpenAI startup key, and AI dependency override."""
    monkeypatch.setenv("SESSION_SECRET_KEY", "integration-test-session-secret")
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-integration-placeholder-not-used")
    # Channel id comes from env (fixture gate ensures it is set).
    channel = os.environ["INTEGRATION_AGENT_CHANNEL_ID"].strip()
    monkeypatch.setenv("AWS_S3_BUCKET", "integration-mock-bucket")

    app = create_app()
    stub = _StubAIClient()
    app.dependency_overrides[_get_openai_client] = lambda: stub
    try:
        yield app, channel
    finally:
        app.dependency_overrides.clear()


def test_agent_turn_hits_team9_poll_and_reply(agent_app: tuple[FastAPI, str]) -> None:
    """Post a unique message via Team 9, then run /agent and assert we processed it and replied."""
    app, channel = agent_app
    probe = f"integration-probe-{uuid.uuid4()}"

    get_client().send_message(channel, probe)

    headers: dict[str, str] = {}
    agent_key = os.environ.get("AGENT_API_KEY", "").strip()
    if agent_key:
        headers["X-API-Key"] = agent_key

    with TestClient(app) as client:
        response = client.post(
            "/agent",
            json={
                "channel_id": channel,
                "container": "integration-mock-bucket",
                "limit": 100,
            },
            headers=headers,
        )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "processed"
    assert body["channel_id"] == channel
    assert body["source_text"] == probe
    assert body["reply"] == f"stub-tools-reply:{probe}"
    assert body.get("sent_message_id")
