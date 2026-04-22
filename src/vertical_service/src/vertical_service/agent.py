"""Agent orchestration: prompt routing, storage tools, and summarize_and_send."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, cast

from ai_client_api.client import AIClient
from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import StorageBackendError
from cloud_storage_api.models import ObjectInfo

from openai_ai_client_impl import OpenAIAIClient


def _object_info_payload(info: ObjectInfo) -> dict[str, Any]:
    """Serialize ObjectInfo for tool results."""
    md = getattr(info, "model_dump", None)
    if callable(md):
        raw = md()
        return cast("dict[str, Any]", raw)
    updated = getattr(info, "updated_at", None)
    updated_s: Any = updated.isoformat() if updated is not None and hasattr(updated, "isoformat") else updated
    return {
        "object_name": info.object_name,
        "size_bytes": info.size_bytes,
        "data_type": info.data_type,
        "version_id": getattr(info, "version_id", None),
        "integrity": info.integrity,
        "encryption": info.encryption,
        "storage_tier": info.storage_tier,
        "updated_at": updated_s,
        "metadata": info.metadata,
    }


def summarize_and_send(  # noqa: PLR0913
    *,
    ai_client: AIClient,
    storage: CloudStorageClient,
    container: str,
    object_key: str,
    send: Callable[[str], None] | None = None,
    max_content_chars: int = 100_000,
) -> dict[str, Any]:
    """Download an object, summarize it with the AI client, optionally deliver via ``send``, and return metadata."""
    with NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        storage.download_file(container=container, object_name=object_key, file_name=str(tmp_path))
        raw = tmp_path.read_bytes()
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    text = raw.decode("utf-8", errors="replace")
    if len(text) > max_content_chars:
        text = text[:max_content_chars] + "\n...[truncated for model context]"

    prompt = (
        "Summarize the following stored file for an operator in chat. "
        "Be concise; use short sections or bullets when helpful.\n\n"
        f"Object key: {object_key}\n\n{text}"
    )
    summary = ai_client.send_message(prompt)
    if send is not None:
        send(summary)
    return {"summary": summary, "object_key": object_key, "container": container}


def _route_prompt(message: str) -> tuple[Literal["summarize_direct", "chat"], str | None]:
    """Classify user text into a direct action or general chat (tool-assisted)."""
    stripped = message.strip()
    lower = stripped.lower()
    if lower.startswith("/summarize "):
        key = stripped.split(maxsplit=1)[1].strip()
        return "summarize_direct", key or None
    return "chat", None


def storage_tool_definitions() -> list[dict[str, Any]]:
    """OpenAI-compatible tool schemas for cloud storage operations."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_storage_files",
                "description": "List object keys in the storage container matching an optional prefix.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prefix": {
                            "type": "string",
                            "description": "Key prefix filter; empty string lists all keys (subject to provider limits).",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_storage_file_info",
                "description": "Return metadata for one object in storage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_key": {"type": "string", "description": "Object key / path in the container."},
                    },
                    "required": ["object_key"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "summarize_storage_file",
                "description": "Download and produce a natural-language summary of a stored file's contents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "object_key": {"type": "string", "description": "Object key to summarize."},
                    },
                    "required": ["object_key"],
                },
            },
        },
    ]


def _make_tool_handler(
    *,
    storage: CloudStorageClient,
    container: str,
    ai_client: AIClient,
) -> Callable[[str, dict[str, Any]], str]:
    def _list_files(args: dict[str, Any]) -> str:
        prefix = args.get("prefix", "") if isinstance(args.get("prefix"), str) else ""
        files = storage.list_files(container, prefix)
        return json.dumps([f.object_name for f in files], default=str)

    def _file_info(args: dict[str, Any]) -> str:
        key = args.get("object_key", "")
        if not isinstance(key, str) or not key:
            return json.dumps({"error": "object_key is required"})
        info = storage.get_file_info(container, key)
        return json.dumps(_object_info_payload(info), default=str)

    def _summarize_file(args: dict[str, Any]) -> str:
        key = args.get("object_key", "")
        if not isinstance(key, str) or not key:
            return json.dumps({"error": "object_key is required"})
        result = summarize_and_send(
            ai_client=ai_client,
            storage=storage,
            container=container,
            object_key=key,
            send=None,
        )
        return json.dumps(result, default=str)

    dispatch: dict[str, Callable[[dict[str, Any]], str]] = {
        "list_storage_files": _list_files,
        "get_storage_file_info": _file_info,
        "summarize_storage_file": _summarize_file,
    }

    def handle_tool(name: str, args: dict[str, Any]) -> str:
        fn = dispatch.get(name)
        if fn is None:
            return json.dumps({"error": f"unknown tool: {name}"})
        try:
            return fn(args)
        except StorageBackendError as exc:
            return json.dumps({"error": str(exc)})

    return handle_tool


def default_storage_container(explicit: str | None) -> str:
    """Resolve bucket/container from request override or environment."""
    if explicit:
        return explicit
    bucket = os.environ.get("AWS_S3_BUCKET")
    if not bucket:
        msg = "No storage container provided and AWS_S3_BUCKET is not set."
        raise RuntimeError(msg)
    return bucket


def run_agent_turn(
    *,
    message: str,
    storage: CloudStorageClient,
    ai: OpenAIAIClient,
    container: str,
    request_context: dict[str, Any] | None = None,
) -> str:
    """Handle one agent message: direct summarize shortcut or OpenAI tool loop."""
    kind, object_key = _route_prompt(message)
    if kind == "summarize_direct" and object_key:
        out = summarize_and_send(
            ai_client=ai,
            storage=storage,
            container=container,
            object_key=object_key,
            send=None,
        )
        return str(out["summary"])

    ctx = request_context or {}
    system = (
        "You help operators work with cloud storage. "
        "Use the provided tools to list objects, inspect metadata, or summarize file contents. "
        "Prefer tools over guessing. Keep final answers concise."
        f"\nRequest context JSON: {json.dumps(ctx, default=str)}"
    )
    reply = ai.run_chat_with_tools(
        system_prompt=system,
        user_message=message,
        tools=storage_tool_definitions(),
        handle_tool=_make_tool_handler(storage=storage, container=container, ai_client=ai),
    )
    return str(reply)
