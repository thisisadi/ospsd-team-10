from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from openai_ai_client_impl.client import OpenAIAIClient


@dataclass
class _Function:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    function: _Function


@dataclass
class _Message:
    content: str | None
    tool_calls: list[_ToolCall] | None = None


@dataclass
class _Choice:
    message: _Message


@dataclass
class _Response:
    choices: list[_Choice]


class _Completions:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _Response:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _OpenAIStub:
    def __init__(self, responses: list[_Response]) -> None:
        self.completions = _Completions(responses)
        self.chat = _Chat(self.completions)


def _response(message: _Message) -> _Response:
    return _Response(choices=[_Choice(message=message)])


def test_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIAIClient()


def test_send_message_uses_mocked_provider() -> None:
    provider = _OpenAIStub([_response(_Message(content="  done  "))])
    client = OpenAIAIClient(api_key="test-key", client=provider)  # type: ignore[arg-type]

    assert client.send_message("hello", {"container": "bucket"}) == "done"
    assert provider.completions.calls[0]["messages"][1] == {"role": "user", "content": "hello"}


def test_tool_loop_executes_real_handler_and_returns_final_text() -> None:
    provider = _OpenAIStub(
        [
            _response(
                _Message(
                    content=None,
                    tool_calls=[_ToolCall(id="call-1", function=_Function("list_storage_files", '{"prefix":"logs/"}'))],
                )
            ),
            _response(_Message(content="Found logs/a.txt")),
        ]
    )
    client = OpenAIAIClient(api_key="test-key", client=provider)  # type: ignore[arg-type]
    seen: list[tuple[str, dict[str, Any]]] = []

    def handle_tool(name: str, args: dict[str, Any]) -> str:
        seen.append((name, args))
        return '["logs/a.txt"]'

    result = client.run_chat_with_tools(
        system_prompt="storage helper",
        user_message="list logs",
        tools=[{"type": "function", "function": {"name": "list_storage_files", "parameters": {}}}],
        handle_tool=handle_tool,
    )

    assert result == "Found logs/a.txt"
    assert seen == [("list_storage_files", {"prefix": "logs/"})]
    assert provider.completions.calls[1]["messages"][-1] == {
        "role": "tool",
        "tool_call_id": "call-1",
        "content": '["logs/a.txt"]',
    }
