"""Service adapter that preserves the original cloud storage interface."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol

from vertical_api.client import (
    Client,
    DeleteResult,
    NotAuthenticatedError,
    ObjectNotFoundError,
    StorageOperationFailedError,
    UploadResult,
)
from vertical_service_api_client.api.storage import (
    delete_object_storage_container_name_objects_object_key_delete as delete_object_api,
)
from vertical_service_api_client.api.storage import (
    download_object_storage_container_name_objects_object_key_get as download_object_api,
)
from vertical_service_api_client.api.storage import (
    list_objects_storage_container_name_objects_get as list_objects_api,
)
from vertical_service_api_client.api.storage import (
    upload_object_storage_container_name_objects_object_key_post as upload_object_api,
)
from vertical_service_api_client.models.http_validation_error import HTTPValidationError

from vertical_service_api_client import Client as ServiceApiClient
from vertical_service_api_client import errors as api_errors

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


def _raise_for_http_status(status_code: HTTPStatus | int) -> None:
    """Map HTTP status codes from the service into port-level exceptions."""
    code = int(status_code)
    if code == HTTPStatus.UNAUTHORIZED:
        msg = "Not authenticated with the storage service."
        raise NotAuthenticatedError(msg)
    if code == HTTPStatus.FORBIDDEN:
        msg = "Forbidden for this storage operation."
        raise NotAuthenticatedError(msg)
    if code == HTTPStatus.NOT_FOUND:
        msg = "Object or container was not found."
        raise ObjectNotFoundError(msg)
    if code == HTTPStatus.UNPROCESSABLE_ENTITY:
        msg = "Request rejected by the storage service (validation error)."
        raise StorageOperationFailedError(msg)
    msg_0 = f"Storage service error (HTTP {code})."
    raise StorageOperationFailedError(msg_0)


class StorageApi(Protocol):
    """Protocol-compatible storage API wrapper used by the adapter."""

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload one object to the remote service (raises on failure)."""

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download one object from the remote service."""

    def delete_object(self, container_name: str, object_name: str) -> DeleteResult:
        """Delete one object on the remote service."""

    def list_objects(self, container_name: str) -> list[str]:
        """List object names in a container."""


class GeneratedStorageApiClient:
    """Wrapper over generated OpenAPI client endpoints."""

    def __init__(self, base_url: str, cookies: Mapping[str, str] | None = None) -> None:
        """Initialize generated client with optional session cookies."""
        self._client = ServiceApiClient(base_url=base_url, cookies=dict(cookies or {}))

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload raw bytes via the generated OpenAPI client upload endpoint."""
        try:
            response = upload_object_api.sync_detailed(
                container_name=container_name,
                object_key=object_name,
                content=data,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        st = response.status_code
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Upload rejected by the storage service."
            raise StorageOperationFailedError(msg) from None
        if st != HTTPStatus.CREATED:
            _raise_for_http_status(st)

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download object bytes via generated endpoint function."""
        try:
            response = download_object_api.sync_detailed(
                container_name=container_name,
                object_key=object_name,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        st = response.status_code
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Download rejected by the storage service."
            raise StorageOperationFailedError(msg) from None
        if st != HTTPStatus.OK:
            _raise_for_http_status(st)
        return getattr(response, "content", b"")

    def delete_object(self, container_name: str, object_name: str) -> DeleteResult:
        """Delete object; map wire response to :class:`DeleteResult` (no dict leakage to callers)."""
        try:
            response = delete_object_api.sync_detailed(
                container_name=container_name,
                object_key=object_name,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        st = response.status_code
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "Delete rejected by the storage service."
            raise StorageOperationFailedError(msg) from None
        if st != HTTPStatus.OK:
            _raise_for_http_status(st)
        if parsed is None:
            return DeleteResult(success=False, object_key=object_name, detail="Empty response from service.")
        try:
            deleted = bool(parsed["deleted"])
        except (KeyError, TypeError):
            deleted = True
        return DeleteResult(
            success=deleted,
            object_key=object_name,
            detail=None if deleted else "Delete was not acknowledged by the service.",
        )

    def list_objects(self, container_name: str) -> list[str]:
        """Return normalized object name list from generated response."""
        try:
            response = list_objects_api.sync_detailed(
                container_name=container_name,
                client=self._client,
            )
        except api_errors.UnexpectedStatus as exc:
            _raise_for_http_status(exc.status_code)
        st = response.status_code
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, HTTPValidationError):
            msg = "List rejected by the storage service."
            raise StorageOperationFailedError(msg) from None
        if st != HTTPStatus.OK:
            _raise_for_http_status(st)
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, str)]
        return []


class CloudStorageServiceAdapter(Client):
    """Implement the cloud storage API contract over HTTP service calls."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        storage_api: StorageApi | None = None,
    ) -> None:
        """Create adapter backed by the service API client."""
        self._storage_api = storage_api or GeneratedStorageApiClient(base_url=base_url)

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> UploadResult:
        """Upload data by delegating to the service API client."""
        self._storage_api.upload_object(container_name, object_name, data)
        return UploadResult(
            success=True,
            container_name=container_name,
            object_key=object_name,
            etag=None,
            detail=None,
        )

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download data by delegating to the service API client."""
        return self._storage_api.download_object(container_name, object_name)

    def delete_object(self, container_name: str, object_name: str) -> DeleteResult:
        """Delete object by delegating to the service API client."""
        return self._storage_api.delete_object(container_name, object_name)

    def list_objects(self, container_name: str) -> Iterator[str]:
        """List objects by delegating to the service API client."""
        return iter(self._storage_api.list_objects(container_name))
