"""Google Cloud Storage implementation of the shared CloudStorageClient API."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO

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
from google.api_core.exceptions import Forbidden, GoogleAPIError, NotFound
from google.cloud import storage  # type: ignore[import-untyped]
from google.oauth2 import service_account  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from datetime import datetime

_GCP_PROJECT_ID = "GCP_PROJECT_ID"
_GCP_CREDENTIALS_PATH = "GCP_CREDENTIALS_PATH"
_GOOGLE_APPLICATION_CREDENTIALS = "GOOGLE_APPLICATION_CREDENTIALS"


class GCPCloudStorageClient(CloudStorageClient):
    """CloudStorageClient implementation backed by Google Cloud Storage."""

    def __init__(self, client: storage.Client | None = None, project_id: str | None = None) -> None:
        """Create a GCS client with explicit client or environment configuration."""
        self._project_id = project_id or os.getenv(_GCP_PROJECT_ID, "").strip()
        self._client: storage.Client | None = client

    @staticmethod
    def _validate_container(container: str) -> None:
        if not container:
            msg = "Container name must not be empty."
            raise InvalidContainerError(msg)

    @staticmethod
    def _validate_object_name(object_name: str) -> None:
        if not object_name:
            msg = "Object name must not be empty."
            raise InvalidObjectNameError(msg)

    def _build_client(self) -> storage.Client:
        if not self._project_id:
            msg = f"Missing required environment variable: {_GCP_PROJECT_ID}"
            raise ValueError(msg)

        credentials_path = os.getenv(_GCP_CREDENTIALS_PATH, "").strip() or os.getenv(_GOOGLE_APPLICATION_CREDENTIALS, "").strip()

        if credentials_path:
            credentials = service_account.Credentials.from_service_account_file(credentials_path)  # type: ignore[no-untyped-call]
            return storage.Client(project=self._project_id, credentials=credentials)
        return storage.Client(project=self._project_id)

    def _ensure_client(self) -> storage.Client:
        if self._client is None:
            self._client = self._build_client()
        return self._client

    @staticmethod
    def _to_object_info(blob: storage.Blob) -> ObjectInfo:
        updated_at: datetime | None = blob.updated if hasattr(blob, "updated") else None
        size_bytes = int(blob.size) if blob.size is not None else None
        version_id = str(blob.generation) if blob.generation is not None else None
        return ObjectInfo(
            object_name=blob.name,
            version_id=version_id,
            data_type=blob.content_type,
            integrity=blob.etag or blob.md5_hash,
            encryption=blob.kms_key_name,
            storage_tier=blob.storage_class,
            size_bytes=size_bytes,
            updated_at=updated_at,
            metadata=blob.metadata,
        )

    def _get_bucket(self, container: str) -> storage.Bucket:
        self._validate_container(container)
        bucket = self._ensure_client().bucket(container)
        try:
            if not bucket.exists():
                msg = f"Container '{container}' not found."
                raise ContainerNotFoundError(msg)
        except Forbidden as exc:
            msg = f"GCP auth failed for container '{container}': {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Container '{container}' not found."
            raise ContainerNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed for container '{container}': {exc}"
            raise StorageBackendError(msg) from exc
        return bucket

    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        """Upload a local file into GCS and return object metadata."""
        self._validate_object_name(remote_path)
        try:
            Path(local_path).stat()
        except OSError as exc:
            msg = f"Cannot read local file '{local_path}': {exc}"
            raise LocalFileAccessError(msg) from exc

        bucket = self._get_bucket(container)
        blob = bucket.blob(remote_path)
        try:
            blob.upload_from_filename(local_path)
            blob.reload()
        except Forbidden as exc:
            msg = f"GCP auth failed ({container}/{remote_path}): {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Container or object not found ({container}/{remote_path}): {exc}"
            raise ObjectNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed ({container}/{remote_path}): {exc}"
            raise StorageBackendError(msg) from exc
        return self._to_object_info(blob)

    def upload_obj(self, container: str, file_obj: BinaryIO, remote_path: str) -> ObjectInfo:
        """Upload a file-like object into GCS and return object metadata."""
        self._validate_object_name(remote_path)
        if file_obj is None or not hasattr(file_obj, "read"):
            msg = "file_obj must be a binary file-like object."
            raise InvalidFileObjectError(msg)
        bucket = self._get_bucket(container)
        blob = bucket.blob(remote_path)
        try:
            blob.upload_from_file(file_obj, rewind=True)
            blob.reload()
        except Forbidden as exc:
            msg = f"GCP auth failed ({container}/{remote_path}): {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Container or object not found ({container}/{remote_path}): {exc}"
            raise ObjectNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed ({container}/{remote_path}): {exc}"
            raise StorageBackendError(msg) from exc
        return self._to_object_info(blob)

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        """Download an object from GCS to local disk and return metadata."""
        self._validate_object_name(object_name)
        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)
        try:
            blob.reload()
            blob.download_to_filename(file_name)
        except OSError as exc:
            msg = f"Cannot write to '{file_name}': {exc}"
            raise LocalFileAccessError(msg) from exc
        except Forbidden as exc:
            msg = f"GCP auth failed ({container}/{object_name}): {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Object '{object_name}' not found in container '{container}'."
            raise ObjectNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed ({container}/{object_name}): {exc}"
            raise StorageBackendError(msg) from exc
        return self._to_object_info(blob)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        """List object metadata in GCS matching the given prefix."""
        bucket = self._get_bucket(container)
        try:
            blobs = list(bucket.list_blobs(prefix=prefix))
        except Forbidden as exc:
            msg = f"GCP auth failed ({container}): {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Container '{container}' not found."
            raise ContainerNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed ({container}): {exc}"
            raise StorageBackendError(msg) from exc
        return sorted([self._to_object_info(blob) for blob in blobs], key=lambda item: item.object_name)

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        """Delete an object from GCS."""
        self._validate_object_name(object_name)
        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)
        try:
            blob.reload()
            blob.delete()
        except Forbidden as exc:
            msg = f"GCP auth failed ({container}/{object_name}): {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Object '{object_name}' not found in container '{container}'."
            raise ObjectNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed ({container}/{object_name}): {exc}"
            raise StorageBackendError(msg) from exc
        return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        """Get metadata for a single object in GCS."""
        self._validate_object_name(object_name)
        bucket = self._get_bucket(container)
        blob = bucket.blob(object_name)
        try:
            blob.reload()
        except Forbidden as exc:
            msg = f"GCP auth failed ({container}/{object_name}): {exc}"
            raise AuthenticationError(msg) from exc
        except NotFound as exc:
            msg = f"Object '{object_name}' not found in container '{container}'."
            raise ObjectNotFoundError(msg) from exc
        except GoogleAPIError as exc:
            msg = f"GCP operation failed ({container}/{object_name}): {exc}"
            raise StorageBackendError(msg) from exc
        return self._to_object_info(blob)
