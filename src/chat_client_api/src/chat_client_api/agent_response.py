"""High-level helper used by the agent endpoint after business logic runs."""

from __future__ import annotations

from chat_client_api.client import get_client


def send_agent_response(channel: str, text: str) -> str:
    """Post the final agent reply to the external chat (Slack) via the registered client.

    This is the only symbol other modules should need for replying to users.

    Args:
        channel: Channel identifier understood by the Team 9 service (e.g. Slack channel id).
        text: Message body to post.

    Returns:
        The remote message id string returned by the chat service.

    """
    return get_client().send_message(channel, text)
