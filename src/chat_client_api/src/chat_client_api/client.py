"""Chat client port (ABC) and dependency-injection factory."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

_NO_CHAT_CLIENT = "No chat client registered. Did you import http_chat_client_impl?"

# Use a mutable container to avoid `global` assignment lint (PLW0603).
_registered_factory: list[Callable[[], ChatClient] | None] = [None]


class ChatClient(ABC):
    """Port for sending messages and checking the remote chat service health (Team 9 API)."""

    @abstractmethod
    def send_message(self, channel: str, text: str) -> str:
        """Send text to a channel on the external chat service and return the new message id."""
        raise NotImplementedError

    @abstractmethod
    def check_health(self) -> bool:
        """Return True if the remote service reports healthy, False otherwise (without raising)."""
        raise NotImplementedError


def register_client_factory(factory: Callable[[], ChatClient]) -> None:
    """Register a factory that produces :class:`ChatClient` instances for dependency injection."""
    _registered_factory[0] = factory


def register_client(client: ChatClient) -> None:
    """Register a concrete :class:`ChatClient` instance (compat: fixed singleton factory)."""
    register_client_factory(lambda: client)


def get_client() -> ChatClient:
    """Return the configured chat client.

    Raises:
        RuntimeError: If no client has been registered (implementation not imported).

    """
    factory = _registered_factory[0]
    if factory is None:
        raise RuntimeError(_NO_CHAT_CLIENT)
    return factory()
