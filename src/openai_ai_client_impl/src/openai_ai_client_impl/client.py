"""OpenAI Chat Completions client with optional tool-calling loop."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any

from ai_client_api.client import AIClient
from openai import OpenAI


class OpenAIAIClient(AIClient):
    """OpenAI implementation of :class:`AIClient` with a synchronous tool loop helper."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: OpenAI | None = None,
    ) -> None:
        """Create a client; reads ``OPENAI_API_KEY`` (and optional ``OPENAI_MODEL``) when ``api_key`` is omitted."""
        key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if not key:
            msg = "OPENAI_API_KEY is not set and no api_key was provided."
            raise RuntimeError(msg)
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._client = client or OpenAI(api_key=key)

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Single-turn chat completion."""
        system = "You are a concise assistant for a cloud storage operations API."
        if context:
            system = f"{system}\nContext JSON: {json.dumps(context, default=str)}"
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        choice = response.choices[0].message
        return (choice.content or "").strip()

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
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]
        rounds = 0
        while rounds < max_tool_rounds:
            rounds += 1
            response = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )  # type: ignore[call-overload]
            msg = response.choices[0].message
            if not msg.tool_calls:
                return (msg.content or "").strip()

            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                raw_args = tc.function.arguments or "{}"
                try:
                    args = json.loads(raw_args)
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}
                result = handle_tool(tc.function.name, args)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    }
                )

        return "Tool loop limit reached; try a narrower request."
