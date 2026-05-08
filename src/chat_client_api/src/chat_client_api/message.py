"""Chat message DTO used by the Team 9 integration boundary."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ChatMessage:
    """Minimal normalized chat message returned by the Team 9 API."""

    message_id: str
    channel: str
    text: str
    sender: str
    timestamp: str
