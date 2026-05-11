"""OpenAI Chat Completions client with optional tool-calling loop."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar, cast

from ai_client_api.client import AIClient
from openai import OpenAI

T = TypeVar("T")


class OpenAIAIClient(AIClient):
    """OpenAI implementation of :class:`AIClient` with a synchronous tool loop helper."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        client: OpenAI | None = None,
        retry_attempts: int = 2,
        retry_backoff_seconds: float = 0.2,
    ) -> None:
        """Create a client; reads ``OPENAI_API_KEY`` (and optional ``OPENAI_MODEL``) when ``api_key`` is omitted."""
        key = api_key if api_key is not None else os.environ.get("OPENAI_API_KEY")
        if not key:
            msg = "OPENAI_API_KEY is not set and no api_key was provided."
            raise RuntimeError(msg)
        self._model = model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        self._client = client or OpenAI(api_key=key)
        self._retry_attempts = max(1, retry_attempts)
        self._retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def _with_retries(self, operation: Callable[[], T]) -> T:
        """Retry transient provider failures without hiding the final exception."""
        last_error: Exception | None = None
        for attempt in range(self._retry_attempts):
            try:
                return operation()
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt == self._retry_attempts - 1:
                    break
                if self._retry_backoff_seconds:
                    time.sleep(self._retry_backoff_seconds * (2**attempt))
        if last_error is None:  # pragma: no cover - defensive; loop always runs at least once.
            msg = "AI request retry loop did not execute."
            raise RuntimeError(msg)
        raise last_error

    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str:
        """Single-turn chat completion."""
        system = "You are a concise assistant for a cloud storage operations API."
        if context:
            system = f"{system}\nContext JSON: {json.dumps(context, default=str)}"
        response = self._with_retries(
            lambda: self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
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
            response = self._with_retries(
                lambda: self._client.chat.completions.create(
                    model=self._model,
                    messages=cast("Any", messages),
                    tools=cast("Any", tools),
                    tool_choice="auto",
                )
            )
            msg = response.choices[0].message
            if not msg.tool_calls:
                return (msg.content or "").strip()

            tool_calls = cast("Any", msg.tool_calls)
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
                        for tc in tool_calls
                    ],
                }
            )
            for tc in tool_calls:
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
