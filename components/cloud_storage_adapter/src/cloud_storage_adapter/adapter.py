"""Service adapter that preserves the original cloud storage interface."""

from __future__ import annotations

from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol
from urllib.parse import quote

from cloud_storage_client_api.client import Client
from cloud_storage_service_api_client import Client as ServiceApiClient
from cloud_storage_service_api_client.api.storage import (
    delete_object_storage_container_name_objects_object_key_delete as delete_object_api,
)
from cloud_storage_service_api_client.api.storage import (
    download_object_storage_container_name_objects_object_key_get as download_object_api,
)
from cloud_storage_service_api_client.api.storage import (
    list_objects_storage_container_name_objects_get as list_objects_api,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


class StorageApi(Protocol):
    """Protocol-compatible storage API wrapper used by the adapter."""

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload one object to the remote service."""

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download one object from the remote service."""

    def delete_object(self, container_name: str, object_name: str) -> bool:
        """Delete one object from the remote service."""

    def list_objects(self, container_name: str) -> list[str]:
        """List object names in a container."""


class GeneratedStorageApiClient:
    """Wrapper over generated OpenAPI client endpoints."""

    def __init__(self, base_url: str, cookies: Mapping[str, str] | None = None) -> None:
        """Initialize generated client with optional session cookies."""
        self._client = ServiceApiClient(base_url=base_url, cookies=dict(cookies or {}))

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload raw bytes using the generated client transport."""
        url = f"/storage/{quote(container_name, safe='')}/objects/{quote(object_name, safe='/')}"
        response = self._client.get_httpx_client().request(method="post", url=url, content=data)
        response.raise_for_status()

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download object bytes via generated endpoint function."""
        response = download_object_api.sync_detailed(
            container_name=container_name,
            object_key=object_name,
            client=self._client,
        )
        if response.status_code != HTTPStatus.OK:
            msg = f"Download failed with status {response.status_code}"
            raise RuntimeError(msg)
        return response.content

    def delete_object(self, container_name: str, object_name: str) -> bool:
        """Delete object and normalize response into a boolean."""
        parsed = delete_object_api.sync(
            container_name=container_name,
            object_key=object_name,
            client=self._client,
        )
        if parsed is None:
            return False
        if "deleted" in parsed:
            return bool(parsed["deleted"])
        return True

    def list_objects(self, container_name: str) -> list[str]:
        """Return normalized object name list from generated response."""
        parsed = list_objects_api.sync(
            container_name=container_name,
            client=self._client,
        )
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

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload data by delegating to the service API client."""
        self._storage_api.upload_object(container_name, object_name, data)

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download data by delegating to the service API client."""
        return self._storage_api.download_object(container_name, object_name)

    def delete_object(self, container_name: str, object_name: str) -> bool:
        """Delete object by delegating to the service API client."""
        return self._storage_api.delete_object(container_name, object_name)

    def list_objects(self, container_name: str) -> Iterator[str]:
        """List objects by delegating to the service API client."""
        return iter(self._storage_api.list_objects(container_name))
