"""HTTP mapping of the cloud storage Client abstract API."""

from __future__ import annotations

from typing import Annotated

from cloud_storage_client_api.client import get_client
from fastapi import APIRouter, Depends, Request, Response, status

from cloud_storage_service.deps import require_oauth_session

router = APIRouter()


@router.get("/{container_name}/objects")
def list_objects(
    container_name: str,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> list[str]:
    """List object names in a container (same contract as Client.list_objects)."""
    return list(get_client().list_objects(container_name))


@router.post(
    "/{container_name}/objects/{object_key:path}",
    status_code=status.HTTP_201_CREATED,
)
async def upload_object(
    container_name: str,
    object_key: str,
    request: Request,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> None:
    """Upload raw bytes as an object (same contract as Client.upload_object)."""
    data = await request.body()
    get_client().upload_object(container_name, object_key, data)


@router.get("/{container_name}/objects/{object_key:path}")
def download_object(
    container_name: str,
    object_key: str,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> Response:
    """Download object bytes (same contract as Client.download_object)."""
    body = get_client().download_object(container_name, object_key)
    return Response(content=body, media_type="application/octet-stream")


@router.delete("/{container_name}/objects/{object_key:path}")
def delete_object(
    container_name: str,
    object_key: str,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> dict[str, bool]:
    """Delete an object (same contract as Client.delete_object)."""
    ok = get_client().delete_object(container_name, object_key)
    return {"deleted": ok}
