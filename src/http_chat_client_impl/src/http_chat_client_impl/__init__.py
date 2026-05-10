"""HTTP-backed Shared-API :class:`chat_client_api.client.ChatClient` (Team 9). Import registers the default factory."""

from __future__ import annotations

from chat_client_api.client import register_client

from http_chat_client_impl.client import HttpChatClient


def _http_chat_client_factory() -> HttpChatClient:
    return HttpChatClient()


register_client(_http_chat_client_factory)

__all__ = ("HttpChatClient",)
