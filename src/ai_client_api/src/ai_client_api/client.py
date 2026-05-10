"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


ToolHandler = Callable[[str, dict[str, Any]], str]

_NO_AI_CLIENT = "No AI client registered. Did you import an implementation?"
_registered_factory: list[Callable[[], AIClient] | None] = [None]


@dataclass(frozen=True)
class ToolDefinition:
    """Provider-neutral function tool definition for model tool calling."""

    name: str
    description: str
    parameters: dict[str, Any]

    def as_openai_tool(self) -> dict[str, Any]:
        """Return a framework-free mapping compatible with OpenAI-style function tools."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class AIClient(ABC):
    """Minimal contract for AI chat completions (per HW3)."""

    @abstractmethod
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Send a user prompt and return the model's text reply."""
        raise NotImplementedError

    @abstractmethod
    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: ToolHandler,
        max_tool_rounds: int = 8,
    ) -> str:
        """Run a model turn that may invoke provider-neutral tool definitions."""
        raise NotImplementedError


def register_client_factory(factory: Callable[[], AIClient]) -> None:
    """Register a provider factory for dependency injection."""
    _registered_factory[0] = factory


def register_client(client: AIClient) -> None:
    """Register a fixed provider instance for tests or local wiring."""
    register_client_factory(lambda: client)


def get_client() -> AIClient:
    """Return the configured AI client implementation."""
    factory = _registered_factory[0]
    if factory is None:
        raise RuntimeError(_NO_AI_CLIENT)
    return factory()
