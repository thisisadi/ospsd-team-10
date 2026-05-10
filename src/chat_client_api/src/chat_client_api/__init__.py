"""Chat client API: port, errors, registry, and :func:`send_agent_response`."""

from __future__ import annotations

from chat_client_api.agent_response import send_agent_response
from chat_client_api.client import (
    ChatClient,
    get_client,
    register_client,
    register_client_factory,
)
from chat_client_api.exceptions import ChatServiceAuthError, ChatServiceError
from chat_client_api.message import ChatMessage

__all__ = (
    "ChatClient",
    "ChatMessage",
    "ChatServiceAuthError",
    "ChatServiceError",
    "get_client",
    "register_client",
    "register_client_factory",
    "send_agent_response",
)
