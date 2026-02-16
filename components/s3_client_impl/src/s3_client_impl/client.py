"""AWS S3 cloud storage client implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

import boto3
from cloud_storage_client_api.client import Client

from s3_client_impl._auth import S3Config, load_s3_config_from_env

if TYPE_CHECKING:
    from collections.abc import Iterator


class _BodyLike(Protocol):
    """Minimal protocol for the streaming body returned by S3."""

    def read(self) -> object: ...


class _S3Like(Protocol):
    """Minimal protocol for the S3 SDK client we call."""

    def put_object(self, *, Bucket: str, Key: str, Body: bytes) -> object: ...  # noqa: N803
    def get_object(self, *, Bucket: str, Key: str) -> dict[str, object]: ...  # noqa: N803
    def delete_object(self, *, Bucket: str, Key: str) -> object: ...  # noqa: N803
    def list_objects_v2(self, *, Bucket: str) -> dict[str, object]: ...  # noqa: N803


@dataclass(frozen=True)
class FileMeta:
    """Represents metadata about a file stored in S3."""

    path: str
    size: int | None = None


class S3CloudStorageClient(Client):
    """Concrete AWS S3 implementation of the Cloud Storage Client interface."""

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

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload data as an object inside a container."""
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket
        s3.put_object(Bucket=bucket, Key=object_name, Body=data)

    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download and return the data of an object from a container."""
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket

        resp = s3.get_object(Bucket=bucket, Key=object_name)
        body = cast("_BodyLike", resp["Body"])
        data = body.read()
        return cast("bytes", data)

    def delete_object(self, container_name: str, object_name: str) -> bool:
        """Delete an object from a container and return True if successful."""
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket
        s3.delete_object(Bucket=bucket, Key=object_name)
        return True

    def list_objects(self, container_name: str) -> Iterator[str]:
        """Return the names of all objects stored in a container."""
        cfg = self._ensure_config()
        s3 = self._ensure_s3()
        bucket = container_name or cfg.bucket

        resp = s3.list_objects_v2(Bucket=bucket)
        contents = resp.get("Contents", [])
        if not isinstance(contents, list):
            return

        for obj in contents:
            if isinstance(obj, dict):
                key = obj.get("Key")
                if isinstance(key, str):
                    yield key
