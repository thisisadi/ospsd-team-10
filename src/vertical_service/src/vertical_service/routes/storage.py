"""HTTP mapping of the cloud storage Client abstract API."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from vertical_api.client import (
    MissingCredentialsError,
    NotAuthenticatedError,
    ObjectNotFoundError,
    StorageError,
    StorageOperationFailedError,
    get_client,
)

from vertical_service.deps import require_oauth_session

router = APIRouter()

_PORT_STORAGE_ERRORS: tuple[type[BaseException], ...] = (
    ObjectNotFoundError,
    NotAuthenticatedError,
    MissingCredentialsError,
    StorageOperationFailedError,
    StorageError,
)


def _storage_http_exception(exc: BaseException) -> HTTPException:
    """Map port-level storage errors to HTTP responses."""
    if isinstance(exc, ObjectNotFoundError):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, NotAuthenticatedError):
        return HTTPException(status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    if isinstance(exc, MissingCredentialsError):
        return HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    if isinstance(exc, StorageOperationFailedError):
        return HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
    if isinstance(exc, StorageError):
        return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    fallback = "Unexpected storage error."
    return HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail=fallback)


@router.get("/{container_name}/objects")
def list_objects(
    container_name: str,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> list[str]:
    """List object names in a container (same contract as Client.list_objects)."""
    try:
        return list(get_client().list_objects(container_name))
    except _PORT_STORAGE_ERRORS as exc:
        raise _storage_http_exception(exc) from exc


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
    try:
        upload_result = get_client().upload_object(container_name, object_key, data)
    except _PORT_STORAGE_ERRORS as exc:
        raise _storage_http_exception(exc) from exc
    if getattr(upload_result, "success", True) is False:
        detail = getattr(upload_result, "error", None) or getattr(upload_result, "detail", None) or "Upload failed."
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(detail))


@router.get("/{container_name}/objects/{object_key:path}")
def download_object(
    container_name: str,
    object_key: str,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> Response:
    """Download object bytes (same contract as Client.download_object)."""
    try:
        body = get_client().download_object(container_name, object_key)
    except _PORT_STORAGE_ERRORS as exc:
        raise _storage_http_exception(exc) from exc
    return Response(content=body, media_type="application/octet-stream")


@router.delete("/{container_name}/objects/{object_key:path}")
def delete_object(
    container_name: str,
    object_key: str,
    _session_id: Annotated[str, Depends(require_oauth_session)],
) -> dict[str, bool]:
    """Delete an object (same contract as Client.delete_object)."""
    try:
        raw = get_client().delete_object(container_name, object_key)
    except _PORT_STORAGE_ERRORS as exc:
        raise _storage_http_exception(exc) from exc
    if hasattr(raw, "success") and raw.success is False:
        detail = getattr(raw, "error", None) or getattr(raw, "detail", None) or "Delete failed."
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(detail))
    deleted = bool(getattr(raw, "success", True)) if hasattr(raw, "success") else bool(raw)
    return {"deleted": deleted}
