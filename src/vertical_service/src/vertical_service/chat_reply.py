"""Post agent replies through the registered shared :class:`chat_client_api.client.ChatClient`."""

from __future__ import annotations

from chat_client_api.client import get_client


def send_agent_response(channel_id: str, text: str) -> str:
    """Send ``text`` to ``channel_id`` and return the remote message id."""
    sent = get_client().send_message(channel_id, text)
    return sent.message_id
