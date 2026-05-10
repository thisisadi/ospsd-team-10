"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


class AIClient(ABC):
    """Minimal contract for AI chat completions (per HW3)."""

    @abstractmethod
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Send a user prompt and return the model's text reply."""

    @abstractmethod
    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: Callable[[str, dict[str, Any]], str],
        max_tool_rounds: int = 8,
    ) -> str:
        """Run a multi-turn completion, executing tool calls until the model responds with text."""


_registered_ai: list[Callable[[], AIClient] | None] = [None]


def register_ai_client(factory: Callable[[], AIClient]) -> None:
    """Register a factory that produces :class:`AIClient` instances."""
    _registered_ai[0] = factory


def get_ai_client() -> AIClient:
    """Return a configured AI client instance from the registered factory."""
    factory = _registered_ai[0]
    if factory is None:
        msg = "No AI client implementation registered. Import openai_ai_client_impl to register the default."
        raise RuntimeError(msg)
    return factory()
