"""AWS S3 cloud storage client implementation."""

from __future__ import annotations

from dataclasses import dataclass

import boto3

from s3_client_impl._auth import S3Config, load_s3_config_from_env


@dataclass(frozen=True)
class FileMeta:
    """Represents metadata about a file stored in S3."""

    path: str
    size: int | None = None


class S3CloudStorageClient:
    """Concrete AWS S3 implementation.

    Notes:
        Later this will inherit from the interface ABC.
        For now, we scaffold the logic.

    """

    def __init__(self, s3: object | None = None, config: S3Config | None = None) -> None:
        """Create an S3-backed cloud storage client."""
        self._config = config or load_s3_config_from_env()
        self._s3 = s3 or boto3.client("s3", region_name=self._config.region)

    def upload(self, local_path: str, remote_path: str) -> str:
        """Upload a file to S3."""
        self._s3.upload_file(local_path, self._config.bucket, remote_path)
        return remote_path

    def download(self, remote_path: str, local_path: str) -> None:
        """Download a file from S3."""
        self._s3.download_file(self._config.bucket, remote_path, local_path)

    def list(self, prefix: str) -> list[FileMeta]:
        """List files in S3 under a prefix."""
        resp = self._s3.list_objects_v2(Bucket=self._config.bucket, Prefix=prefix)
        contents = resp.get("Contents", [])

        out: list[FileMeta] = []
        for obj in contents:
            key = obj.get("Key")
            if isinstance(key, str):
                size = obj.get("Size")
                out.append(FileMeta(path=key, size=size if isinstance(size, int) else None))
        return out

    def delete(self, remote_path: str) -> None:
        """Delete file from S3."""
        self._s3.delete_object(Bucket=self._config.bucket, Key=remote_path)
