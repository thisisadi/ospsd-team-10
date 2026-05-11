"""HTTP mapping of the shared CloudStorageClient API."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Annotated, Any, cast

from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from fastapi import APIRouter, Depends, HTTPException, Request, Response, UploadFile, status

from vertical_service.deps import require_oauth_session

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient

router = APIRouter(prefix="/files")

_STORAGE_ERRORS: tuple[type[BaseException], ...] = (
    ObjectNotFoundError,
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidObjectNameError,
    LocalFileAccessError,
    StorageBackendError,
)

_EXCEPTION_STATUS_MAP: dict[type[BaseException], int] = {
    ObjectNotFoundError: status.HTTP_404_NOT_FOUND,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    ContainerNotFoundError: status.HTTP_404_NOT_FOUND,
    InvalidContainerError: HTTPStatus.UNPROCESSABLE_ENTITY,
    InvalidObjectNameError: HTTPStatus.UNPROCESSABLE_ENTITY,
    LocalFileAccessError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    StorageBackendError: status.HTTP_502_BAD_GATEWAY,
}


def _to_http(exc: BaseException) -> HTTPException:
    for exc_type, status_code in _EXCEPTION_STATUS_MAP.items():
        if isinstance(exc, exc_type):
            return HTTPException(status_code=status_code, detail=str(exc))
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected storage error.",
    )


def _get_storage_client(request: Request) -> CloudStorageClient:
    return cast("CloudStorageClient", request.app.state.storage_client)


def _serialize(obj: object) -> dict[str, Any]:
    """Convert any storage SDK object into a JSON-safe dict."""
    if isinstance(obj, dict):
        return cast("dict[str, Any]", obj)
    if hasattr(obj, "model_dump"):
        return cast("dict[str, Any]", obj.model_dump())
    if hasattr(obj, "to_dict"):
        return cast("dict[str, Any]", obj.to_dict())
    return {key: getattr(obj, key) for key in dir(obj) if not key.startswith("_")}


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    remote_path: str,
    file: UploadFile,
) -> dict[str, Any]:
    """Upload file to storage."""
    try:
        result = _get_storage_client(request).upload_obj(
            container=container,
            file_obj=file.file,
            remote_path=remote_path,
        )
    except _STORAGE_ERRORS as exc:
        raise _to_http(exc) from exc

    return _serialize(result)


@router.get("/download")
def download_file(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    object_name: str,
) -> Response:
    """Download file from storage."""
    tmp_path: Path | None = None

    try:
        with NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        _get_storage_client(request).download_file(
            container=container,
            object_name=object_name,
            file_name=str(tmp_path),
        )

        with tmp_path.open("rb") as f:
            content = f.read()

    except _STORAGE_ERRORS as exc:
        raise _to_http(exc) from exc

    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

    return Response(content=content, media_type="application/octet-stream")


@router.get("/list")
def list_files(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    prefix: str = "",
) -> list[dict[str, Any]]:
    """List files in storage container."""
    try:
        result = _get_storage_client(request).list_files(
            container=container,
            prefix=prefix,
        )
    except _STORAGE_ERRORS as exc:
        raise _to_http(exc) from exc

    return [_serialize(item) for item in result]


@router.delete("/delete")
def delete_file(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    object_name: str,
) -> dict[str, Any]:
    """Delete file from storage."""
    try:
        result = _get_storage_client(request).delete_file(
            container=container,
            object_name=object_name,
        )
    except _STORAGE_ERRORS as exc:
        raise _to_http(exc) from exc

    return _serialize(result)


@router.get("/info")
def get_file_info(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    object_name: str,
) -> dict[str, Any]:
    """Get file metadata."""
    try:
        result = _get_storage_client(request).get_file_info(
            container=container,
            object_name=object_name,
        )
    except _STORAGE_ERRORS as exc:
        raise _to_http(exc) from exc

    return _serialize(result)
