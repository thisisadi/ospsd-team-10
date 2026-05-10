from __future__ import annotations

import pytest
from ai_client_api.client import ToolHandler

from ai_client_api import AIClient, ToolDefinition, get_client, register_client


class FakeAIClient(AIClient):
    def send_message(self, prompt: str, context: dict[str, object] | None = None) -> str:
        return f"{prompt}:{context or {}}"

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, object]],
        handle_tool: ToolHandler,
        max_tool_rounds: int = 8,
    ) -> str:
        _ = (system_prompt, tools, handle_tool, max_tool_rounds)
        return user_message


def test_tool_definition_serializes_without_provider_types() -> None:
    tool = ToolDefinition(
        name="list_storage_files",
        description="List files",
        parameters={"type": "object", "properties": {"prefix": {"type": "string"}}},
    )

    assert tool.as_openai_tool() == {
        "type": "function",
        "function": {
            "name": "list_storage_files",
            "description": "List files",
            "parameters": {"type": "object", "properties": {"prefix": {"type": "string"}}},
        },
    }


def test_registry_returns_registered_client() -> None:
    fake = FakeAIClient()
    register_client(fake)

    assert get_client() is fake
    assert get_client().send_message("hello") == "hello:{}"


def test_abstract_base_requires_methods() -> None:
    with pytest.raises(TypeError):
        AIClient()  # type: ignore[abstract]
