from __future__ import annotations

from types import SimpleNamespace
from typing import Protocol

import httpx
from http_chat_client_impl.client import HttpChatClient


class MonkeyPatchLike(Protocol):
    def setenv(self, name: str, value: str, prepend: str | None = None) -> None: ...

    def setattr(self, target: str, value: object, *, raising: bool = True) -> None: ...


def test_send_message_falls_back_to_raw_http_when_generated_parser_breaks(monkeypatch: MonkeyPatchLike) -> None:
    monkeypatch.setenv("CHAT_SERVICE_BASE_URL", "https://chat.example.com")
    monkeypatch.setenv("CHAT_SESSION_ID", "session-123")

    monkeypatch.setattr(
        "http_chat_client_impl.client.OpenApiClient.get_httpx_client",
        lambda self: SimpleNamespace(  # noqa: ARG005
            request=lambda *args, **kwargs: SimpleNamespace(  # noqa: ARG005
                status_code=200,
                content=b'{"message_id":"m-123","channel":"C1","text":"hello"}',
            )
        ),
    )

    client = HttpChatClient()
    assert client.send_message("C1", "hello") == "m-123"


def test_send_message_reads_message_id_from_raw_content_when_parsed_is_none(monkeypatch: MonkeyPatchLike) -> None:
    monkeypatch.setenv("CHAT_SERVICE_BASE_URL", "https://chat.example.com")
    monkeypatch.setenv("CHAT_SESSION_ID", "session-123")

    monkeypatch.setattr(
        "http_chat_client_impl.client.OpenApiClient.get_httpx_client",
        lambda self: SimpleNamespace(  # noqa: ARG005
            request=lambda *args, **kwargs: SimpleNamespace(  # noqa: ARG005
                status_code=200,
                content=b'{"message_id":"m-xyz","channel":"C2"}',
            )
        ),
    )

    client = HttpChatClient()
    assert client.send_message("C2", "ping") == "m-xyz"


def test_send_message_uses_single_request_call(monkeypatch: MonkeyPatchLike) -> None:
    monkeypatch.setenv("CHAT_SERVICE_BASE_URL", "https://chat.example.com")
    monkeypatch.setenv("CHAT_SESSION_ID", "session-123")
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def _request(*args: object, **kwargs: object) -> object:
        calls.append((args, kwargs))
        return SimpleNamespace(
            status_code=200,
            content=b'{"message_id":"m-abc","channel":"C1","text":"hello"}',
        )

    monkeypatch.setattr(
        "http_chat_client_impl.client.OpenApiClient.get_httpx_client",
        lambda self: SimpleNamespace(request=_request),  # noqa: ARG005
    )

    client = HttpChatClient()
    assert client.send_message("C1", "hello") == "m-abc"
    assert len(calls) == 1


def test_send_message_retries_transient_network_failure(monkeypatch: MonkeyPatchLike) -> None:
    monkeypatch.setenv("CHAT_SERVICE_BASE_URL", "https://chat.example.com")
    monkeypatch.setenv("CHAT_SESSION_ID", "session-123")
    calls = 0

    def _request(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        _ = (args, kwargs)
        if calls == 1:
            request = httpx.Request("POST", "https://chat.example.com/messages")
            msg = "temporary network failure"
            raise httpx.ConnectError(msg, request=request)
        return SimpleNamespace(
            status_code=200,
            content=b'{"message_id":"m-retry","channel":"C1","text":"hello"}',
        )

    monkeypatch.setattr(
        "http_chat_client_impl.client.OpenApiClient.get_httpx_client",
        lambda self: SimpleNamespace(request=_request),  # noqa: ARG005
    )

    client = HttpChatClient(retry_attempts=2, retry_backoff_seconds=0)
    assert client.send_message("C1", "hello") == "m-retry"
    assert calls == 2
