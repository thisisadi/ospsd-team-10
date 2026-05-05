"""AWS S3 cloud storage client implementation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Protocol, TypedDict, cast

import boto3
from botocore.exceptions import ClientError
from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from cloud_storage_api.models import DeleteResult, ObjectInfo

from vertical_impl._auth import S3Config, load_s3_config_from_env


class _BodyLike(Protocol):
    """Minimal protocol for the streaming body returned by S3."""

    def read(self) -> bytes: ...


class _GetObjectOutput(TypedDict):
    """get_object response shape. Body is always present for successful responses."""

    Body: _BodyLike


class _HeadObjectOutput(TypedDict, total=False):
    ContentLength: int
    ContentType: str
    ETag: str
    VersionId: str
    ServerSideEncryption: str
    StorageClass: str
    LastModified: datetime
    Metadata: dict[str, str]


class _S3Like(Protocol):
    """Minimal protocol for the S3 SDK client we call."""

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> object: ...  # noqa: N803
    def put_object_from_fileobj(self, *, Bucket: str, Key: str, Body: BinaryIO) -> object: ...  # noqa: N803
    def get_object(self, *, Bucket: str, Key: str) -> _GetObjectOutput: ...  # noqa: N803
    def delete_object(self, *, Bucket: str, Key: str) -> dict[str, Any]: ...  # noqa: N803
    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict[str, Any]: ...  # noqa: N803
    def head_object(self, *, Bucket: str, Key: str) -> _HeadObjectOutput: ...  # noqa: N803
    def download_file(self, Bucket: str, Key: str, Filename: str) -> None: ...  # noqa: N803
    def upload_fileobj(self, Fileobj: BinaryIO, Bucket: str, Key: str) -> None: ...  # noqa: N803


class S3CloudStorageClient(CloudStorageClient):
    """Concrete AWS S3 implementation of the shared CloudStorageClient interface."""

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

    def _validate_container(self, container: str) -> None:
        """Raise if container name is empty."""
        if not container:
            msg = "Container name must not be empty."
            raise InvalidContainerError(msg)

    def _validate_object_name(self, object_name: str) -> None:
        """Raise if object name is empty."""
        if not object_name:
            msg = "Object name must not be empty."
            raise InvalidObjectNameError(msg)

    @staticmethod
    def _map_client_error(exc: ClientError, *, resource: str) -> None:
        """Translate botocore ClientError into shared interface exceptions."""
        err = exc.response.get("Error", {}) if isinstance(exc.response, dict) else {}
        code = err.get("Code", "") if isinstance(err, dict) else ""
        if code in {"401", "403", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
            msg = f"S3 auth failed ({resource}): {exc}"
            raise AuthenticationError(msg) from exc
        if code == "NoSuchBucket":
            msg = f"Bucket not found ({resource}): {exc}"
            raise ContainerNotFoundError(msg) from exc
        if code in {"NoSuchKey", "404"}:
            msg = f"Object not found ({resource}): {exc}"
            raise ObjectNotFoundError(msg) from exc
        msg = f"S3 operation failed ({resource}): {exc}"
        raise StorageBackendError(msg) from exc

    @staticmethod
    def _build_object_info(object_name: str, head: _HeadObjectOutput) -> ObjectInfo:
        """Map a HeadObject response dict to a shared ObjectInfo."""
        raw_ts = head.get("LastModified")
        updated_at: datetime | None = None
        if isinstance(raw_ts, datetime):
            updated_at = raw_ts
        elif isinstance(raw_ts, str):
            updated_at = datetime.fromisoformat(raw_ts)
        return ObjectInfo(
            object_name=object_name,
            version_id=head.get("VersionId"),
            data_type=head.get("ContentType"),
            integrity=head.get("ETag"),
            encryption=head.get("ServerSideEncryption"),
            storage_tier=head.get("StorageClass"),
            size_bytes=head.get("ContentLength"),
            updated_at=updated_at,
            metadata=head.get("Metadata"),
        )

    # ------------------------------------------------------------------ #
    # CloudStorageClient interface                                         #
    # ------------------------------------------------------------------ #

    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        """Upload a local file to cloud storage."""
        self._validate_container(container)
        self._validate_object_name(remote_path)
        s3 = self._ensure_s3()
        try:
            with Path(local_path).open("rb") as f:
                data = f.read()
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}': {exc}"
            raise LocalFileAccessError(msg) from exc
        try:
            s3.put_object(Bucket=container, Key=remote_path, Body=data)
            head = s3.head_object(Bucket=container, Key=remote_path)
            return self._build_object_info(remote_path, head)
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{container}/{remote_path}")
            raise

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        """Upload a binary file-like object to cloud storage."""
        self._validate_container(container)
        self._validate_object_name(remote_path)
        s3 = self._ensure_s3()
        if file_obj is None or not hasattr(file_obj, "read"):
            msg = "file_obj must be a binary file-like object."
            raise InvalidFileObjectError(msg)
        try:
            s3.upload_fileobj(file_obj, container, remote_path)
            head = s3.head_object(Bucket=container, Key=remote_path)
            return self._build_object_info(remote_path, head)
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{container}/{remote_path}")
            raise

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        """Download a file from cloud storage to a local path."""
        self._validate_container(container)
        self._validate_object_name(object_name)
        s3 = self._ensure_s3()
        try:
            s3.download_file(container, object_name, file_name)
            head = s3.head_object(Bucket=container, Key=object_name)
            return self._build_object_info(object_name, head)
        except OSError as exc:
            msg = f"Cannot write to '{file_name}': {exc}"
            raise LocalFileAccessError(msg) from exc
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{container}/{object_name}")
            raise

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List files in cloud storage matching a prefix."""
        self._validate_container(container)
        s3 = self._ensure_s3()
        try:
            resp = s3.list_objects_v2(Bucket=container, Prefix=prefix)
        except ClientError as exc:
            self._map_client_error(exc, resource=container)
            raise

        contents = resp.get("Contents", [])
        if not isinstance(contents, list):
            return []

        results: list[ObjectInfo] = []
        for obj in contents:
            if not isinstance(obj, dict):
                continue
            key = obj.get("Key")
            if not isinstance(key, str):
                continue
            raw_ts = obj.get("LastModified")
            updated_at: datetime | None = None
            if isinstance(raw_ts, datetime):
                updated_at = raw_ts
            results.append(
                ObjectInfo(
                    object_name=key,
                    size_bytes=obj.get("Size"),
                    integrity=obj.get("ETag"),
                    storage_tier=obj.get("StorageClass"),
                    updated_at=updated_at,
                )
            )
        return sorted(results, key=lambda o: o.object_name)

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete a file from cloud storage."""
        self._validate_container(container)
        self._validate_object_name(object_name)
        s3 = self._ensure_s3()
        try:
            s3.head_object(Bucket=container, Key=object_name)
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{container}/{object_name}")
            raise

        try:
            resp = s3.delete_object(Bucket=container, Key=object_name)
            return DeleteResult(
                deleted=True,
                version_id=resp.get("VersionId") if isinstance(resp, dict) else None,
                request_charged=resp.get("RequestCharged") == "requester" if isinstance(resp, dict) else None,
            )
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{container}/{object_name}")
            raise

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Return metadata for a single stored object."""
        self._validate_container(container)
        self._validate_object_name(object_name)
        s3 = self._ensure_s3()
        try:
            head = s3.head_object(Bucket=container, Key=object_name)
            return self._build_object_info(object_name, head)
        except ClientError as exc:
            self._map_client_error(exc, resource=f"{container}/{object_name}")
            raise
