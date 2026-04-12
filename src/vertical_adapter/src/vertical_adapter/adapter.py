"""Service adapter implementing the shared CloudStorageClient interface over HTTP."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Protocol

from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import (
    AuthenticationError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from cloud_storage_api.models import DeleteResult, ObjectInfo
from vertical_service_api_client.api.storage import (
    delete_file_storage_files_delete_delete as delete_file_api,
)
from vertical_service_api_client.api.storage import (
    download_file_storage_files_download_get as download_file_api,
)
from vertical_service_api_client.api.storage import (
    get_file_info_storage_files_info_get as get_file_info_api,
)
from vertical_service_api_client.api.storage import (
    list_files_storage_files_list_get as list_files_api,
)
from vertical_service_api_client.api.storage import (
    upload_file_storage_files_upload_post as upload_file_api,
)
from vertical_service_api_client.models.body_upload_file_storage_files_upload_post import (
    BodyUploadFileStorageFilesUploadPost,
)
from vertical_service_api_client.models.http_validation_error import HTTPValidationError

from vertical_service_api_client import Client as ServiceApiClient
from vertical_service_api_client import errors as api_errors

if TYPE_CHECKING:
    from collections.abc import Mapping


def _raise_for_http_status(status_code: HTTPStatus | int) -> None:
    """Map HTTP status codes from the service into shared domain exceptions."""
    code = int(status_code)
    if code in {HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN}:
        msg = f"Not authenticated with the storage service (HTTP {code})."
        raise AuthenticationError(msg)
    if code == HTTPStatus.NOT_FOUND:
        msg = "Object or container was not found."
        raise ObjectNotFoundError(msg)
    if code == HTTPStatus.UNPROCESSABLE_ENTITY:
        msg = "Request rejected by the storage service (validation error)."
        raise InvalidObjectNameError(msg)
    msg = f"Storage service error (HTTP {code})."
    raise StorageBackendError(msg)


class StorageApi(Protocol):
    """Protocol for the internal HTTP API wrapper used by the adapter."""

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        """Upload a file-like object to the remote service."""

    def download_file(self, container: str, object_name: str) -> bytes:
        """Download one object from the remote service."""

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete one object on the remote service."""

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List objects in a container."""

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Return metadata for a single object."""


class GeneratedStorageApiClient:
    """Wrapper over the generated OpenAPI client endpoints."""

    def __init__(self, base_url: str, cookies: Mapping[str, str] | None = None) -> None:
        """Initialize with base URL and optional session cookies."""
        self._client = ServiceApiClient(base_url=base_url, cookies=dict(cookies or {}))

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        """Upload a file-like object via the generated upload endpoint."""
        try:
            response = upload_file_api.sync_detailed(
                container=container,
                remote_path=remote_path,
                body=BodyUploadFileStorageFilesUploadPost(file=file_obj),
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Upload rejected by the storage service."
            raise StorageBackendError(msg)
        if response.status_code != HTTPStatus.CREATED:
            _raise_for_http_status(response.status_code)
        return _parse_object_info(parsed)

    def download_file(self, container: str, object_name: str) -> bytes:
        """Download object bytes via the generated download endpoint."""
        try:
            response = download_file_api.sync_detailed(
                container=container,
                object_name=object_name,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Download rejected by the storage service."
            raise StorageBackendError(msg)
        if response.status_code != HTTPStatus.OK:
            _raise_for_http_status(response.status_code)
        return getattr(response, "content", b"")

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete an object via the generated delete endpoint."""
        try:
            response = delete_file_api.sync_detailed(
                container=container,
                object_name=object_name,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Delete rejected by the storage service."
            raise StorageBackendError(msg)
        if response.status_code != HTTPStatus.OK:
            _raise_for_http_status(response.status_code)
        if parsed is None:
            return DeleteResult(deleted=False, version_id=None, request_charged=None)
        try:
            return DeleteResult(
                deleted=bool(parsed["deleted"]),
                version_id=parsed.get("version_id"),
                request_charged=parsed.get("request_charged"),
            )
        except (KeyError, TypeError):
            return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """Return normalized object list from the generated list endpoint."""
        try:
            response = list_files_api.sync_detailed(
                container=container,
                prefix=prefix,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "List rejected by the storage service."
            raise StorageBackendError(msg)
        if response.status_code != HTTPStatus.OK:
            _raise_for_http_status(response.status_code)
        if not isinstance(parsed, list):
            return []
        return [_parse_object_info(item) for item in parsed if item is not None]

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Fetch object metadata via the generated info endpoint."""
        try:
            response = get_file_info_api.sync_detailed(
                container=container,
                object_name=object_name,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Info rejected by the storage service."
            raise StorageBackendError(msg)
        if response.status_code != HTTPStatus.OK:
            _raise_for_http_status(response.status_code)
        return _parse_object_info(parsed)


def _parse_object_info(raw: object) -> ObjectInfo:
    """Convert a wire response object or dict into a shared ObjectInfo."""
    if isinstance(raw, dict):
        return ObjectInfo(
            object_name=raw.get("object_name", ""),
            version_id=raw.get("version_id"),
            data_type=raw.get("data_type"),
            integrity=raw.get("integrity"),
            encryption=raw.get("encryption"),
            storage_tier=raw.get("storage_tier"),
            size_bytes=raw.get("size_bytes"),
            updated_at=raw.get("updated_at"),
            metadata=raw.get("metadata"),
        )
    return ObjectInfo(
        object_name=getattr(raw, "object_name", ""),
        version_id=getattr(raw, "version_id", None),
        data_type=getattr(raw, "data_type", None),
        integrity=getattr(raw, "integrity", None),
        encryption=getattr(raw, "encryption", None),
        storage_tier=getattr(raw, "storage_tier", None),
        size_bytes=getattr(raw, "size_bytes", None),
        updated_at=getattr(raw, "updated_at", None),
        metadata=getattr(raw, "metadata", None),
    )


class CloudStorageServiceAdapter(CloudStorageClient):
    """Implement the shared CloudStorageClient contract over HTTP service calls."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        storage_api: StorageApi | None = None,
    ) -> None:
        """Create adapter backed by the service API client."""
        self._storage_api = storage_api or GeneratedStorageApiClient(base_url=base_url)

    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        """Read local file and upload via the service API."""
        try:
            with Path(local_path).open("rb") as f:
                return self._storage_api.upload_obj(container, f, remote_path)
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}': {exc}"
            raise LocalFileAccessError(msg) from exc

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        """Upload a file-like object via the service API."""
        return self._storage_api.upload_obj(container, file_obj, remote_path)

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        """Download object and write to local path."""
        content = self._storage_api.download_file(container, object_name)
        try:
            with Path(file_name).open("wb") as f:
                f.write(content)
        except OSError as exc:
            msg = f"Cannot write to '{file_name}': {exc}"
            raise LocalFileAccessError(msg) from exc
        return ObjectInfo(object_name=object_name, size_bytes=len(content))

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List files via the service API."""
        return self._storage_api.list_files(container, prefix)

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete a file via the service API."""
        return self._storage_api.delete_file(container, object_name)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Get file metadata via the service API."""
        return self._storage_api.get_file_info(container, object_name)
