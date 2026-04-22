"""Tests for HW3 agent route and summarize_and_send orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
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
        self.calls.append(kwargs)
        msg = _FakeMessage(content="default") if not self._replies else self._replies.pop(0)
        return _FakeCompletion(msg)


class _FakeChat:
    def __init__(self, replies: list[_FakeMessage]) -> None:
        self.completions = _FakeCompletions(replies)


class _FakeOpenAI:
    def __init__(self, replies: list[_FakeMessage]) -> None:
        self.chat = _FakeChat(replies)


@pytest.fixture
def fake_openai_client() -> OpenAIAIClient:
    """OpenAI client backed by a stub transport (no network)."""
    return OpenAIAIClient(
        api_key="test-key",
        client=_FakeOpenAI([_FakeMessage(content="**Summary:** hello")]),  # type: ignore[arg-type]
    )


def test_summarize_and_send_truncates_and_invokes_send(fake_openai_client: OpenAIAIClient) -> None:
    delivered: list[str] = []
    storage = MagicMock()

    def _download(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_text("long text", encoding="utf-8")
        return object()

    storage.download_file.side_effect = _download

    out = summarize_and_send(
        ai_client=fake_openai_client,
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


def test_agent_summarize_shortcut_returns_summary(
    monkeypatch: pytest.MonkeyPatch,
    fake_openai_client: OpenAIAIClient,
) -> None:
    monkeypatch.setenv("AWS_S3_BUCKET", "unit-bucket")
    app = create_app()
    app.state.ai_client = fake_openai_client
    storage = MagicMock()

    def _download(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_bytes(b"file body")
        return object()

    storage.download_file.side_effect = _download
    app.state.storage_client = storage

    client = TestClient(app)
    res = client.post("/agent", json={"message": "/summarize report.md"})
    assert res.status_code == 200
    body = res.json()
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


def test_make_tool_handler_summarize_tool(fake_openai_client: OpenAIAIClient) -> None:
    storage = MagicMock()

    def _dl(*, container: str, object_name: str, file_name: str) -> object:  # noqa: ARG001
        Path(file_name).write_bytes(b"yo")
        return object()

    storage.download_file.side_effect = _dl
    handler = _make_tool_handler(storage=storage, container="c", ai_client=fake_openai_client)
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


def test_agent_requires_service_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_SERVICE_KEY", "secret")
    monkeypatch.setenv("AWS_S3_BUCKET", "b")
    app = create_app()
    app.state.ai_client = OpenAIAIClient(
        api_key="k",
        client=_FakeOpenAI([_FakeMessage(content="x")]),  # type: ignore[arg-type]
    )
    app.state.storage_client = MagicMock()
    client = TestClient(app)
    res = client.post("/agent", json={"message": "/summarize a.txt"})
    assert res.status_code == 401

    res_ok = client.post(
        "/agent",
        json={"message": "/summarize a.txt"},
        headers={"X-Service-Key": "secret"},
    )
    assert res_ok.status_code == 200
