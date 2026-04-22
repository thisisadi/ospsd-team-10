"""Abstract base class for AI providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AIClient(ABC):
    """Minimal contract for AI chat completions (per HW3)."""

    @abstractmethod
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Send a user prompt and return the model's text reply."""
