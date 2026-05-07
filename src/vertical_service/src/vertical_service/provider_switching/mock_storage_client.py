"""In-memory mock implementation of the shared CloudStorageClient API."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import (
    InvalidContainerError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
)
from cloud_storage_api.models import DeleteResult, ObjectInfo


@dataclass(slots=True)
class _StoredObject:
    data: bytes
    data_type: str | None
    metadata: dict[str, str] = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class MockCloudStorageClient(CloudStorageClient):
    """CloudStorageClient implementation that stores objects in memory."""

    def __init__(self) -> None:
        """Initialize empty in-memory storage."""
        self._store: dict[str, dict[str, _StoredObject]] = {}

    @staticmethod
    def _validate_container(container: str) -> None:
        if not container:
            msg = "Container name must not be empty."
            raise InvalidContainerError(msg)

    @staticmethod
    def _validate_object_name(object_name: str) -> None:
        if not object_name:
            msg = "Object name must not be empty."
            raise InvalidObjectNameError(msg)

    def _get_object(self, container: str, object_name: str) -> _StoredObject:
        try:
            return self._store[container][object_name]
        except KeyError as exc:
            msg = f"Object '{object_name}' not found in container '{container}'."
            raise ObjectNotFoundError(msg) from exc

    @staticmethod
    def _to_info(object_name: str, obj: _StoredObject) -> ObjectInfo:
        return ObjectInfo(
            object_name=object_name,
            data_type=obj.data_type,
            size_bytes=len(obj.data),
            updated_at=obj.updated_at,
            metadata=obj.metadata,
        )

    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        """Upload a local file from disk into in-memory storage."""
        self._validate_container(container)
        self._validate_object_name(remote_path)
        try:
            payload = Path(local_path).read_bytes()
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}': {exc}"
            raise LocalFileAccessError(msg) from exc
        return self._save_bytes(container=container, object_name=remote_path, payload=payload)

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        """Upload a file-like object into in-memory storage."""
        self._validate_container(container)
        self._validate_object_name(remote_path)
        payload = file_obj.read()
        if not isinstance(payload, bytes):
            msg = "file_obj.read() must return bytes."
            raise LocalFileAccessError(msg)
        content_type = getattr(file_obj, "content_type", None)
        metadata = getattr(file_obj, "headers", None)
        normalized_metadata: dict[str, str] = {}
        if metadata is not None and hasattr(metadata, "items"):
            normalized_metadata = {str(key): str(value) for key, value in metadata.items()}
        return self._save_bytes(
            container=container,
            object_name=remote_path,
            payload=payload,
            content_type=content_type if isinstance(content_type, str) else None,
            metadata=normalized_metadata,
        )

    def _save_bytes(
        self,
        *,
        container: str,
        object_name: str,
        payload: bytes,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> ObjectInfo:
        bucket = self._store.setdefault(container, {})
        bucket[object_name] = _StoredObject(
            data=payload,
            data_type=content_type,
            metadata=metadata or {},
        )
        return self._to_info(object_name, bucket[object_name])

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        """Download an in-memory object to the provided local file path."""
        self._validate_container(container)
        self._validate_object_name(object_name)
        obj = self._get_object(container, object_name)
        try:
            Path(file_name).write_bytes(obj.data)
        except OSError as exc:
            msg = f"Cannot write to '{file_name}': {exc}"
            raise LocalFileAccessError(msg) from exc
        return self._to_info(object_name, obj)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List object metadata for names matching the given prefix."""
        self._validate_container(container)
        container_objects = self._store.get(container, {})
        matching_names = sorted(name for name in container_objects if name.startswith(prefix))
        return [self._to_info(name, container_objects[name]) for name in matching_names]

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete an object from in-memory storage."""
        self._validate_container(container)
        self._validate_object_name(object_name)
        container_objects = self._store.get(container, {})
        if object_name not in container_objects:
            msg = f"Object '{object_name}' not found in container '{container}'."
            raise ObjectNotFoundError(msg)
        del container_objects[object_name]
        if not container_objects:
            self._store.pop(container, None)
        return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Get metadata for an object stored in memory."""
        self._validate_container(container)
        self._validate_object_name(object_name)
        return self._to_info(object_name, self._get_object(container, object_name))
