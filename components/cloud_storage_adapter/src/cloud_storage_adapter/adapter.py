"""Service adapter that preserves the original cloud storage interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from cloud_storage_client_api.client import Client
from cloud_storage_service_api_client import ApiClient, StorageApiClient

if TYPE_CHECKING:
    from collections.abc import Iterator


class CloudStorageServiceAdapter(Client):
    """Implement the cloud storage API contract over HTTP service calls."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        storage_api: StorageApiClient | None = None,
    ) -> None:
        """Create adapter backed by the service API client."""
        self._storage_api = storage_api or StorageApiClient(api_client=ApiClient(base_url=base_url))

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
