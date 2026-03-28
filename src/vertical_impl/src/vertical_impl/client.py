"""AWS S3 cloud storage client implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypedDict, cast

import boto3
from botocore.exceptions import ClientError
from vertical_api.client import Client, ObjectNotFoundError, StorageOperationFailedError

from vertical_impl._auth import S3Config, load_s3_config_from_env

if TYPE_CHECKING:
    from collections.abc import Iterator


class _BodyLike(Protocol):
    """Minimal protocol for the streaming body returned by S3. Matches botocore StreamingBody."""

    def read(self) -> bytes: ...


class _GetObjectOutput(TypedDict):
    """get_object response shape. Body is always present for successful responses."""

    Body: _BodyLike


class _S3Like(Protocol):
    """Minimal protocol for the S3 SDK client we call."""

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> object: ...  # noqa: N803
    def get_object(self, *, Bucket: str, Key: str) -> _GetObjectOutput: ...  # noqa: N803
    def delete_object(self, *, Bucket: str, Key: str) -> object: ...  # noqa: N803
    def list_objects_v2(self, *, Bucket: str) -> dict[str, object]: ...  # noqa: N803


@dataclass(frozen=True)
class FileMeta:
    """Represents metadata about a file stored in S3."""

    path: str
    size: int | None = None


class S3CloudStorageClient(Client):
    """Concrete AWS S3 implementation of the Cloud Storage Client interface."""

    @dataclass(frozen=True)
    class UploadObjectResult:
        """Outcome of a single S3 upload attempt (success flag, key, metadata, error)."""

        success: bool
        object_key: str
        metadata: dict[str, Any] | None
        error: str | None

    @dataclass(frozen=True)
    class DeleteObjectResult:
        """Outcome of a single S3 delete attempt (success flag, key, error)."""

        success: bool
        object_key: str
        error: str | None

    def __init__(self, s3: _S3Like | None = None, config: S3Config | None = None) -> None:
        """Create an S3-backed cloud storage client."""
        self._config: S3Config | None = config
        self._s3: _S3Like | None = s3

    def _ensure_config(self) -> S3Config:
        """Return config, loading from env vars if needed."""
        if self._config is None:
            self._config = load_s3_config_from_env()
        return self._config

    def _ensure_s3(self) -> _S3Like:
        """Return an S3 client, creating one if needed."""
        if self._s3 is None:
            cfg = self._ensure_config()
            self._s3 = cast("_S3Like", boto3.client("s3", region_name=cfg.region))
        return self._s3

    @staticmethod
    def _map_client_error(exc: ClientError, *, resource: str) -> None:
        """Translate botocore errors into port-level storage exceptions."""
        err = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
        code = err.get("Code", "") if isinstance(err, dict) else ""
        if code in {"NoSuchKey", "NoSuchBucket", "404"}:
            msg = f"S3 resource not found ({resource}): {exc}"
            raise ObjectNotFoundError(msg) from exc
        msg = f"S3 operation failed ({resource}): {exc}"
        raise StorageOperationFailedError(msg) from exc

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> S3CloudStorageClient.UploadObjectResult:
        """Upload data as an object inside a container.

        Returns:
            UploadObjectResult: Structured result indicating success or failure.

        """
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket

        try:
            response = s3.put_object(Bucket=bucket, Key=object_name, Body=data)

            metadata = None
            if isinstance(response, dict):
                metadata = {
                    "etag": response.get("ETag"),
                    "version_id": response.get("VersionId"),
                }

            return self.UploadObjectResult(
                success=True,
                object_key=object_name,
                metadata=metadata,
                error=None,
            )

        except ClientError as e:
            return self.UploadObjectResult(
                success=False,
                object_key=object_name,
                metadata=None,
                error=f"Upload failed: {e!s}",
            )

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download and return the data of an object from a container."""
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket

        try:
            resp = s3.get_object(Bucket=bucket, Key=object_name)
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{bucket}/{object_name}")
        body = resp["Body"]
        return body.read()

    def delete_object(self, container_name: str, object_name: str) -> S3CloudStorageClient.DeleteObjectResult:
        """Delete an object from a container.

        Returns:
            DeleteObjectResult: Indicates if deletion was successful,
            and provides the object_key and any error message.

        """
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket

        try:
            s3.delete_object(Bucket=bucket, Key=object_name)
            return self.DeleteObjectResult(
                success=True,
                object_key=object_name,
                error=None,
            )
        except ClientError as e:
            return self.DeleteObjectResult(
                success=False,
                object_key=object_name,
                error=f"Delete failed: {e!s}",
            )

    def list_objects(self, container_name: str) -> Iterator[str]:
        """Return the names of all objects stored in a container."""
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket

        try:
            resp = s3.list_objects_v2(Bucket=bucket)
        except ClientError as exc:
            self._map_client_error(exc, resource=bucket)

        contents = resp.get("Contents", [])
        if not isinstance(contents, list):
            return

        for obj in contents:
            if isinstance(obj, dict):
                key = obj.get("Key")
                if isinstance(key, str):
                    yield key
