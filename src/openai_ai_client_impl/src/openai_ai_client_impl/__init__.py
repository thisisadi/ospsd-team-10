"""OpenAI-backed AI client implementation."""

from __future__ import annotations

from ai_client_api.client import register_ai_client

from openai_ai_client_impl.client import OpenAIAIClient


def _openai_from_env() -> OpenAIAIClient:
    return OpenAIAIClient()


register_ai_client(_openai_from_env)

__all__ = ["OpenAIAIClient"]
