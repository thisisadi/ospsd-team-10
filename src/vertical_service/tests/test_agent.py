"""Tests for HW3 agent route and summarize_and_send orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import vertical_service.routes.agent as agent_routes
from cloud_storage_api.exceptions import StorageBackendError
from fastapi.testclient import TestClient
from openai_ai_client_impl.client import OpenAIAIClient
from vertical_service.agent import (
    _make_tool_handler,
    _object_info_payload,
    default_storage_container,
    run_agent_turn,
    storage_tool_definitions,
    summarize_and_send,
)
from vertical_service.app import create_app

from chat_client_api import ChatMessage


class _FakeMessage:
    def __init__(self, *, content: str | None = "ok", tool_calls: object | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, msg: _FakeMessage) -> None:
        self.message = msg


class _FakeCompletion:
    def __init__(self, msg: _FakeMessage) -> None:
        self.choices = [_FakeChoice(msg)]


class _FakeCompletions:
    def __init__(self, replies: list[_FakeMessage]) -> None:
        self._replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: object) -> _FakeCompletion:
        self.calls.append(cast("dict[str, Any]", kwargs))
        msg = _FakeMessage(content="default") if not self._replies else self._replies.pop(0)
        return _FakeCompletion(msg)


class _FakeChat:
    def __init__(self, replies: list[_FakeMessage]) -> None:
        self.completions = _FakeCompletions(replies)


class _FakeOpenAI:
    def __init__(self, replies: list[_FakeMessage]) -> None:
        self.chat = _FakeChat(replies)


class DummyAIClient:
    """Local stand-in for the real OpenAI client used by agent tests."""

    def __init__(self, replies: list[_FakeMessage] | None = None) -> None:
        """Initialize the dummy AI client."""
        self._client = _FakeOpenAI(replies or [_FakeMessage(content="**Summary:** hello")])

    def send_message(self, prompt: str) -> str:
        """Return a deterministic summary string for tests."""
        _ = prompt
        return "**Summary:** hello"

    def run_chat_with_tools(
        self,
        *,
        user_message: str,
        system_prompt: str,
        tools: list[dict[str, Any]],
        handle_tool: object,
    ) -> str:
        """Return a deterministic tool-loop response for tests."""
        _ = (user_message, system_prompt, tools, handle_tool)
        return "from-tools"


class _StubChatClient:
    """Small chat-client stub for polling tests."""

    def __init__(self, messages: list[ChatMessage]) -> None:
        """Store fixed messages returned by get_messages."""
        self._messages = messages

    def get_messages(self, _channel: str, *, limit: int = 10, cursor: str | None = None) -> list[ChatMessage]:
        """Return the configured message list."""
        _ = (limit, cursor)
        return self._messages


class _FakeToolFunction:
    def __init__(self, *, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _FakeToolCall:
    def __init__(self, *, call_id: str, name: str, arguments: str) -> None:
        self.id = call_id
        self.function = _FakeToolFunction(name=name, arguments=arguments)


@pytest.fixture
def fake_openai_client() -> DummyAIClient:
    """AI client backed by a stub transport with no external dependency."""
    return DummyAIClient([_FakeMessage(content="**Summary:** hello")])


def test_summarize_and_send_truncates_and_invokes_send(fake_openai_client: DummyAIClient) -> None:
    delivered: list[str] = []
    storage = MagicMock()

    def _download(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_text("long text", encoding="utf-8")
        return object()

    storage.download_file.side_effect = _download

    out = summarize_and_send(
        ai_client=cast("Any", fake_openai_client),
        storage=storage,
        container="bucket",
        object_key="notes.txt",
        send=delivered.append,
        max_content_chars=4,
    )
    assert out["object_key"] == "notes.txt"
    assert out["summary"] == "**Summary:** hello"
    assert delivered == ["**Summary:** hello"]
    storage.download_file.assert_called_once()


def test_summarize_and_send_caps_large_reads(fake_openai_client: DummyAIClient) -> None:
    storage = MagicMock()

    def _download(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_bytes(b"x" * 50)
        return object()

    storage.download_file.side_effect = _download
    out = summarize_and_send(
        ai_client=cast("Any", fake_openai_client),
        storage=storage,
        container="bucket",
        object_key="huge.txt",
        max_content_chars=8,
    )
    assert out["summary"] == "**Summary:** hello"
    storage.download_file.assert_called_once()


def test_agent_summarize_shortcut_returns_summary(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_client: DummyAIClient,
) -> None:
    monkeypatch.setenv("AWS_S3_BUCKET", "unit-bucket")
    app = create_app()
    app.state.ai_client = fake_openai_client
    storage = MagicMock()
    app.state.storage_client = storage
    app.state.processed_chat_message_ids = set()
    app.state.last_processed_chat_timestamps = {}

    messages = [
        ChatMessage(
            message_id="m-1",
            channel="C1",
            text="/summarize report.md",
            sender="aditya",
            timestamp="100.0",
        ),
    ]

    def _download(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_bytes(b"file body")
        return object()

    storage.download_file.side_effect = _download
    monkeypatch.setattr(agent_routes, "get_client", lambda: _StubChatClient(messages))
    monkeypatch.setattr(agent_routes, "send_agent_response", lambda _channel, _text: "msg-1")

    client = TestClient(app)
    res = client.post("/agent", json={"channel_id": "C1"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "processed"
    assert body["reply"] == "**Summary:** hello"
    storage.download_file.assert_called_once()


def test_storage_tool_definitions_count() -> None:
    assert len(storage_tool_definitions()) == 3


def test_default_storage_container_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_S3_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="AWS_S3_BUCKET"):
        default_storage_container(None)
    monkeypatch.setenv("AWS_S3_BUCKET", "my-bucket")
    assert default_storage_container(None) == "my-bucket"
    assert default_storage_container("override") == "override"


def test_object_info_payload_model_dump() -> None:
    info = MagicMock()
    info.model_dump.return_value = {"object_name": "k"}
    assert _object_info_payload(info) == {"object_name": "k"}


def test_make_tool_handler_list_and_errors() -> None:
    storage = MagicMock()
    o1 = MagicMock()
    o1.object_name = "x.txt"
    storage.list_files.return_value = [o1]
    ai = MagicMock()
    handler = _make_tool_handler(storage=storage, container="c", ai_client=ai)

    out = handler("list_storage_files", {"prefix": "pre"})
    assert "x.txt" in out
    storage.list_files.assert_called_once_with("c", "pre")

    bad_info = handler("get_storage_file_info", {})
    assert "error" in bad_info

    unknown = handler("nope", {})
    assert "unknown tool" in unknown


def test_make_tool_handler_file_info_and_storage_error() -> None:
    storage = MagicMock()
    meta = MagicMock()
    meta.object_name = "a"
    meta.size_bytes = 3
    meta.data_type = "text/plain"
    meta.integrity = None
    meta.encryption = None
    meta.storage_tier = None
    meta.updated_at = None
    meta.metadata = None
    storage.get_file_info.return_value = meta
    ai = MagicMock()
    handler = _make_tool_handler(storage=storage, container="c", ai_client=ai)

    out = handler("get_storage_file_info", {"object_key": "a"})
    assert "a" in out
    storage.get_file_info.assert_called_once_with("c", "a")

    storage.get_file_info.side_effect = StorageBackendError("backend down")
    err_out = handler("get_storage_file_info", {"object_key": "k"})
    assert "backend down" in err_out


def test_make_tool_handler_summarize_tool(fake_openai_client: DummyAIClient) -> None:
    storage = MagicMock()

    def _dl(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_bytes(b"yo")
        return object()

    storage.download_file.side_effect = _dl
    handler = _make_tool_handler(
        storage=storage,
        container="c",
        ai_client=cast("Any", fake_openai_client),
    )
    raw = handler("summarize_storage_file", {"object_key": "f.txt"})
    assert "summary" in raw.lower() or "Summary" in raw


def test_run_agent_turn_delegates_to_tool_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_S3_BUCKET", "b")
    storage = MagicMock()
    ai = MagicMock()
    ai.run_chat_with_tools.return_value = "from-tools"

    reply = run_agent_turn(message="list my files", storage=storage, ai=ai, container="bkt")
    assert reply == "from-tools"
    ai.run_chat_with_tools.assert_called_once()


def test_run_agent_turn_with_real_openai_client_tools() -> None:
    storage = MagicMock()
    o1 = MagicMock()
    o1.object_name = "report.txt"
    storage.list_files.return_value = [o1]

    first_msg = _FakeMessage(
        content=None,
        tool_calls=[_FakeToolCall(call_id="call_1", name="list_storage_files", arguments='{"prefix": ""}')],
    )
    second_msg = _FakeMessage(content="Found one file: report.txt")
    fake_transport = _FakeOpenAI([first_msg, second_msg])
    ai = OpenAIAIClient(api_key="test-key", client=cast("Any", fake_transport))

    reply = run_agent_turn(message="list files", storage=storage, ai=ai, container="bucket")

    assert reply == "Found one file: report.txt"
    storage.list_files.assert_called_once_with("bucket", "")
    first_call = fake_transport.chat.completions.calls[0]
    assert "tools" in first_call


def test_agent_requires_service_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("AWS_S3_BUCKET", "b")
    app = create_app()
    app.state.ai_client = DummyAIClient([_FakeMessage(content="x")])
    app.state.storage_client = MagicMock()
    monkeypatch.setattr(agent_routes, "get_client", lambda: _StubChatClient([]))
    client = TestClient(app)

    res = client.post("/agent", json={"channel_id": "C1"})
    assert res.status_code == 401

    res_ok = client.post(
        "/agent",
        json={"channel_id": "C1"},
        headers={"X-API-Key": "secret"},
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["status"] == "idle"


def test_agent_posts_reply_to_chat_when_channel_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_API_KEY", "secret")
    monkeypatch.setenv("AWS_S3_BUCKET", "b")
    app = create_app()
    app.state.ai_client = DummyAIClient([_FakeMessage(content="reply-from-ai")])
    app.state.storage_client = MagicMock()

    sent: list[tuple[str, str]] = []

    def _fake_send(channel: str, text: str) -> str:
        sent.append((channel, text))
        return "msg-123"

    messages = [
        ChatMessage(
            message_id="m-1",
            channel="C123",
            text="hello",
            sender="aditya",
            timestamp="100.0",
        ),
    ]

    monkeypatch.setattr(agent_routes, "get_client", lambda: _StubChatClient(messages))
    monkeypatch.setattr(agent_routes, "send_agent_response", _fake_send)

    client = TestClient(app)
    res = client.post(
        "/agent",
        json={"channel_id": "C123"},
        headers={"X-API-Key": "secret"},
    )

    assert res.status_code == 200
    assert sent == [("C123", "from-tools")]
    assert res.json()["sent_message_id"] == "msg-123"


def test_agent_returns_idle_when_no_new_messages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_S3_BUCKET", "b")
    app = create_app()
    app.state.ai_client = DummyAIClient([_FakeMessage(content="reply-from-ai")])
    app.state.storage_client = MagicMock()
    app.state.processed_chat_message_ids = {"m-1"}
    app.state.last_processed_chat_timestamps = {"C123": "100.0"}

    messages = [
        ChatMessage(
            message_id="m-1",
            channel="C123",
            text="hello",
            sender="aditya",
            timestamp="100.0",
        ),
    ]

    monkeypatch.setattr(agent_routes, "get_client", lambda: _StubChatClient(messages))
    send_mock = MagicMock(return_value="msg-123")
    monkeypatch.setattr(agent_routes, "send_agent_response", send_mock)

    client = TestClient(app)
    res = client.post("/agent", json={"channel_id": "C123"})

    assert res.status_code == 200
    assert res.json()["status"] == "idle"
    send_mock.assert_not_called()
