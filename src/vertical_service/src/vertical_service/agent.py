"""Agent orchestration: prompt routing, storage tools, and summarize_and_send."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Protocol, cast

from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import StorageBackendError
from cloud_storage_api.models import ObjectInfo
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class CreateStorageContainerArgs(BaseModel):
    """Validated args for the create_storage_container tool."""

    model_config = ConfigDict(extra="forbid")

    container: str | None = Field(
        default=None,
        description="Container or bucket name to create. Defaults to active container.",
    )


class UploadTextAsFileArgs(BaseModel):
    """Validated args for the upload_text_as_file tool."""

    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(description="Object key/path for the file.", min_length=1)
    text: str = Field(description="Text content to upload.")


class ListStorageFilesArgs(BaseModel):
    """Validated args for the list_storage_files tool."""

    model_config = ConfigDict(extra="forbid")

    prefix: str = Field(default="", description="Key prefix filter; empty string lists all keys.")


class ObjectKeyArgs(BaseModel):
    """Validated args for tools that operate on a single object key."""

    model_config = ConfigDict(extra="forbid")

    object_key: str = Field(description="Object key or path in the container.", min_length=1)


class AIClient(Protocol):
    """Minimal interface required from the AI client."""

    def send_message(self, prompt: str) -> str:
        """Return a text response for a plain prompt."""

    def run_chat_with_tools(
        self,
        *,
        system_prompt: str,
        user_message: str,
        tools: list[dict[str, Any]],
        handle_tool: Callable[[str, dict[str, Any]], str],
    ) -> str:
        """Run a tool-enabled chat turn and return the final response."""


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
    """Download an object, summarize it, optionally send it, and return metadata."""
    with NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        storage.download_file(container=container, object_name=object_key, file_name=str(tmp_path))
        # Bound memory use for unexpectedly large objects by reading only a capped prefix.
        max_bytes = max(max_content_chars + 1, 1)
        with tmp_path.open("rb") as handle:
            raw = handle.read(max_bytes)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    text = raw.decode("utf-8", errors="replace")
    if len(raw) > max_content_chars or len(text) > max_content_chars:
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
    """Classify user text into a direct action or general chat."""
    stripped = message.strip()
    lower = stripped.lower()
    if lower.startswith("/summarize "):
        key = stripped.split(maxsplit=1)[1].strip()
        return "summarize_direct", key or None
    return "chat", None


def storage_tool_definitions() -> list[dict[str, Any]]:
    """Return tool schemas for cloud storage operations."""
    return [
        {
            "type": "function",
            "function": {
                "name": "create_storage_container",
                "description": "Create a storage container/bucket if the provider supports it.",
                "parameters": CreateStorageContainerArgs.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "upload_text_as_file",
                "description": "Create or overwrite a text file in storage.",
                "parameters": UploadTextAsFileArgs.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_storage_files",
                "description": "List object keys in the storage container matching an optional prefix.",
                "parameters": ListStorageFilesArgs.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_storage_file_info",
                "description": "Return metadata for one object in storage.",
                "parameters": ObjectKeyArgs.model_json_schema(),
            },
        },
        {
            "type": "function",
            "function": {
                "name": "summarize_storage_file",
                "description": "Download and summarize a stored file.",
                "parameters": ObjectKeyArgs.model_json_schema(),
            },
        },
    ]


def _validation_error_payload(exc: ValidationError) -> str:
    """Serialize tool-argument validation failures for the model."""
    return json.dumps({"error": "invalid tool arguments", "details": exc.errors()})


def _make_tool_handler(  # noqa: C901, PLR0915
    *,
    storage: CloudStorageClient,
    container: str,
    ai_client: AIClient,
) -> Callable[[str, dict[str, Any]], str]:
    """Build the storage tool dispatcher."""

    def _create_container(args: dict[str, Any]) -> str:
        try:
            parsed = CreateStorageContainerArgs.model_validate(args)
        except ValidationError as exc:
            return _validation_error_payload(exc)
        target_container = parsed.container or container
        if not target_container:
            return json.dumps({"error": "container must be a non-empty string"})

        # Support provider-specific extension methods when available.
        create_container = getattr(storage, "create_container", None)
        if callable(create_container):
            create_container(target_container)
            return json.dumps({"created": True, "container": target_container})

        create_bucket = getattr(storage, "create_bucket", None)
        if callable(create_bucket):
            create_bucket(target_container)
            return json.dumps({"created": True, "container": target_container})

        # S3-specific fallback for current implementation.
        ensure_s3 = getattr(storage, "_ensure_s3", None)
        if callable(ensure_s3):
            s3 = ensure_s3()
            region = os.environ.get("AWS_REGION", "us-east-1")
            if region == "us-east-1":
                s3.create_bucket(Bucket=target_container)
            else:
                s3.create_bucket(
                    Bucket=target_container,
                    CreateBucketConfiguration={"LocationConstraint": region},
                )
            return json.dumps({"created": True, "container": target_container})

        return json.dumps({"error": "active storage provider does not support container creation"})

    def _upload_text(args: dict[str, Any]) -> str:
        try:
            parsed = UploadTextAsFileArgs.model_validate(args)
        except ValidationError as exc:
            return _validation_error_payload(exc)
        object_key = parsed.object_key
        text = parsed.text

        payload = text.encode("utf-8")

        upload_obj = getattr(storage, "upload_obj", None)
        if callable(upload_obj):
            result = upload_obj(container, BytesIO(payload), object_key)
            return json.dumps(
                {
                    "uploaded": True,
                    "container": container,
                    "object_key": object_key,
                    "result": _object_info_payload(result),
                },
                default=str,
            )

        upload_file = getattr(storage, "upload_file", None)
        if callable(upload_file):
            with NamedTemporaryFile(delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                tmp_path.write_bytes(payload)
                result = upload_file(container=container, local_path=str(tmp_path), remote_path=object_key)
            finally:
                if tmp_path.exists():
                    tmp_path.unlink()
            return json.dumps(
                {
                    "uploaded": True,
                    "container": container,
                    "object_key": object_key,
                    "result": _object_info_payload(result),
                },
                default=str,
            )

        return json.dumps({"error": "active storage provider does not support upload"})

    def _list_files(args: dict[str, Any]) -> str:
        try:
            parsed = ListStorageFilesArgs.model_validate(args)
        except ValidationError as exc:
            return _validation_error_payload(exc)
        files = storage.list_files(container, parsed.prefix)
        return json.dumps([f.object_name for f in files], default=str)

    def _file_info(args: dict[str, Any]) -> str:
        try:
            parsed = ObjectKeyArgs.model_validate(args)
        except ValidationError as exc:
            return _validation_error_payload(exc)
        info = storage.get_file_info(container, parsed.object_key)
        return json.dumps(_object_info_payload(info), default=str)

    def _summarize_file(args: dict[str, Any]) -> str:
        try:
            parsed = ObjectKeyArgs.model_validate(args)
        except ValidationError as exc:
            return _validation_error_payload(exc)
        result = summarize_and_send(
            ai_client=ai_client,
            storage=storage,
            container=container,
            object_key=parsed.object_key,
            send=None,
        )
        return json.dumps(result, default=str)

    dispatch: dict[str, Callable[[dict[str, Any]], str]] = {
        "create_storage_container": _create_container,
        "upload_text_as_file": _upload_text,
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
        except Exception as exc:  # noqa: BLE001
            return json.dumps({"error": str(exc)})

    return handle_tool


def default_storage_container(explicit: str | None) -> str:
    """Resolve bucket or container from request override or environment."""
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
    ai: AIClient,
    container: str,
    request_context: dict[str, Any] | None = None,
) -> str:
    """Handle one agent message."""
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
