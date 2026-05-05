"""HTTP-backed :class:`chat_client_api.ChatClient` (Team 9). Importing this package registers the default client."""

from __future__ import annotations

from http_chat_client_impl.client import HttpChatClient

__all__ = ("HttpChatClient",)
