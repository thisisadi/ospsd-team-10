"""Storage endpoint wrapper used by the adapter layer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cloud_storage_service_api_client.client import ApiClient

from cloud_storage_service_api_client.client import RequestOptions


@dataclass(slots=True)
class StorageApiClient:
    """Typed wrapper for cloud storage service endpoints."""

    api_client: ApiClient

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload bytes to the service."""
        self.api_client.request(
            "POST",
            "/storage/upload",
            options=RequestOptions(
                params={"container_name": container_name, "object_name": object_name},
                content=data,
                extra_headers={"Content-Type": "application/octet-stream"},
            ),
        )

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download bytes from the service."""
        response = self.api_client.request(
            "GET",
            "/storage/download",
            options=RequestOptions(params={"container_name": container_name, "object_name": object_name}),
        )
        return response.content

    def delete_object(self, container_name: str, object_name: str) -> bool:
        """Delete one object on the service."""
        self.api_client.request(
            "DELETE",
            "/storage/delete",
            options=RequestOptions(params={"container_name": container_name, "object_name": object_name}),
        )
        return True

    def list_objects(self, container_name: str) -> list[str]:
        """List object names from the service."""
        response = self.api_client.request(
            "GET",
            "/storage/list",
            options=RequestOptions(params={"container_name": container_name}),
        )
        payload = response.json()
        return _parse_list_payload(payload)


def _parse_list_payload(payload: object) -> list[str]:
    """Normalize common list response payloads."""
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, str)]

    if isinstance(payload, dict):
        objects = payload.get("objects")
        if isinstance(objects, list):
            return [item for item in objects if isinstance(item, str)]

    return []
