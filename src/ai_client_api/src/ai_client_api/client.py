"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, TypeAlias

ToolHandler: TypeAlias = Callable[[str, dict[str, Any]], Any]


class AIClient(ABC):
    """Minimal contract for AI chat completions (per HW3)."""

    @abstractmethod
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Send a user prompt and return the model's text reply."""

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, object]],
        handle_tool: ToolHandler,
        max_tool_rounds: int = 8,
    ) -> str:
        """Run a tool-capable chat flow.

        Implementations can override this; the default keeps older clients usable.
        """
        _ = (system_prompt, tools, handle_tool, max_tool_rounds)
        return self.send_message(user_message)


@dataclass(frozen=True)
class ToolDefinition:
    """Provider-neutral function tool definition."""

    name: str
    description: str
    parameters: Mapping[str, object]

    def as_openai_tool(self) -> dict[str, object]:
        """Return this definition in OpenAI function-tool format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": dict(self.parameters),
            },
        }


_client: AIClient | None = None
_ERR_NO_CLIENT = "No AI client has been registered."


def register_client(client: AIClient) -> None:
    """Register the process-wide AI client implementation."""
    global _client  # noqa: PLW0603
    _client = client


def get_client() -> AIClient:
    """Return the registered process-wide AI client implementation."""
    if _client is None:
        raise RuntimeError(_ERR_NO_CLIENT)
    return _client
