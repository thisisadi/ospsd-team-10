"""Abstract AI client API for chat completions (HW3)."""

from __future__ import annotations

from ai_client_api.client import AIClient, ToolDefinition, ToolHandler, get_client, register_client

__all__ = ["AIClient", "ToolDefinition", "ToolHandler", "get_client", "register_client"]
