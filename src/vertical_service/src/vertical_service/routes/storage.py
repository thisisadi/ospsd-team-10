"""HTTP mapping of the shared CloudStorageClient API."""

from __future__ import annotations

import time
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Annotated

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
from vertical_service.metrics import (
    FAILURE_COUNT,
    REQUEST_COUNT,
    REQUEST_LATENCY,
    SUCCESS_COUNT,
)

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
    InvalidContainerError: status.HTTP_422_UNPROCESSABLE_ENTITY,
    InvalidObjectNameError: status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    return request.app.state.storage_client


# -----------------------------
# Upload
# -----------------------------
@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_file(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    remote_path: str,
    file: UploadFile,
) -> dict:
    endpoint = "/storage/files/upload"
    method = "POST"

    REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
    start_time = time.perf_counter()

    try:
        result = _get_storage_client(request).upload_obj(
            container=container,
            file_obj=file.file,
            remote_path=remote_path,
        )
    except _STORAGE_ERRORS as exc:
        FAILURE_COUNT.labels(endpoint=endpoint, method=method).inc()
        raise _to_http(exc) from exc

    SUCCESS_COUNT.labels(endpoint=endpoint, method=method).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(time.perf_counter() - start_time)

    return result.to_dict() if hasattr(result, "to_dict") else dict(result)


# -----------------------------
# Download
# -----------------------------
@router.get("/download")
def download_file(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    object_name: str,
) -> Response:
    endpoint = "/storage/files/download"
    method = "GET"

    REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
    start_time = time.perf_counter()

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
        FAILURE_COUNT.labels(endpoint=endpoint, method=method).inc()
        raise _to_http(exc) from exc

    finally:
        REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(time.perf_counter() - start_time)
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

    SUCCESS_COUNT.labels(endpoint=endpoint, method=method).inc()
    return Response(content=content, media_type="application/octet-stream")


# -----------------------------
# List
# -----------------------------
@router.get("/list")
def list_files(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    prefix: str = "",
) -> list[dict]:
    endpoint = "/storage/files/list"
    method = "GET"

    REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
    start_time = time.perf_counter()

    try:
        result = _get_storage_client(request).list_files(
            container=container,
            prefix=prefix,
        )
    except _STORAGE_ERRORS as exc:
        FAILURE_COUNT.labels(endpoint=endpoint, method=method).inc()
        raise _to_http(exc) from exc

    SUCCESS_COUNT.labels(endpoint=endpoint, method=method).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(time.perf_counter() - start_time)

    return [r.to_dict() if hasattr(r, "to_dict") else dict(r) for r in result]


# -----------------------------
# Delete
# -----------------------------
@router.delete("/delete")
def delete_file(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    object_name: str,
) -> dict:
    endpoint = "/storage/files/delete"
    method = "DELETE"

    REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
    start_time = time.perf_counter()

    try:
        result = _get_storage_client(request).delete_file(
            container=container,
            object_name=object_name,
        )
    except _STORAGE_ERRORS as exc:
        FAILURE_COUNT.labels(endpoint=endpoint, method=method).inc()
        raise _to_http(exc) from exc

    SUCCESS_COUNT.labels(endpoint=endpoint, method=method).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(time.perf_counter() - start_time)

    return result.to_dict() if hasattr(result, "to_dict") else dict(result)


# -----------------------------
# Info
# -----------------------------
@router.get("/info")
def get_file_info(
    _session_id: Annotated[str, Depends(require_oauth_session)],
    request: Request,
    container: str,
    object_name: str,
) -> dict:
    endpoint = "/storage/files/info"
    method = "GET"

    REQUEST_COUNT.labels(endpoint=endpoint, method=method).inc()
    start_time = time.perf_counter()

    try:
        result = _get_storage_client(request).get_file_info(
            container=container,
            object_name=object_name,
        )
    except _STORAGE_ERRORS as exc:
        FAILURE_COUNT.labels(endpoint=endpoint, method=method).inc()
        raise _to_http(exc) from exc

    SUCCESS_COUNT.labels(endpoint=endpoint, method=method).inc()
    REQUEST_LATENCY.labels(endpoint=endpoint, method=method).observe(time.perf_counter() - start_time)

    return result.to_dict() if hasattr(result, "to_dict") else dict(result)