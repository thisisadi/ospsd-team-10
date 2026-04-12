# ruff: noqa: ARG002
"""Tests for storage endpoints."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import ObjectNotFoundError, StorageBackendError
from cloud_storage_api.models import DeleteResult, ObjectInfo
from fastapi.testclient import TestClient
from vertical_impl.token_store import TokenData, store_token
from vertical_service.app import create_app
from vertical_service.deps import require_oauth_session

if TYPE_CHECKING:
    from collections.abc import Generator

    from fastapi import FastAPI

pytestmark = pytest.mark.unit

_MSG_NO_BUCKET = "no bucket"
_MSG_S3_DOWN = "s3 down"

_FAKE_OBJECT_INFO = ObjectInfo(
    object_name="path/to/obj",
    size_bytes=5,
    integrity="etag123",
)


class _FakeClient(CloudStorageClient):
    """Minimal fake used only to assert routing and DI wiring."""

    def __init__(self) -> None:
        self.last_upload: tuple[str, object, str] | None = None

    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        self.last_upload = (container, local_path, remote_path)
        return ObjectInfo(object_name=remote_path)

    def upload_obj(self, container: str, file_obj: object, remote_path: str) -> ObjectInfo:
        self.last_upload = (container, file_obj, remote_path)
        return ObjectInfo(object_name=remote_path)

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        with Path(file_name).open("wb") as f:
            f.write(b"payload")
        return ObjectInfo(object_name=object_name)

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        return [ObjectInfo(object_name="a.txt"), ObjectInfo(object_name="b.txt")]

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        return ObjectInfo(object_name=object_name)


def _make_authenticated_app(
    fake: CloudStorageClient,
) -> tuple[TestClient, FastAPI]:
    """Wire a fake storage client into the app and bypass OAuth."""
    app = create_app()
    app.state.storage_client = fake
    store_token(
        "test-session",
        TokenData(access_token="test-access-token", token_type="Bearer", expires_at=None),  # noqa: S106
    )
    app.dependency_overrides[require_oauth_session] = lambda: "test-session"
    return TestClient(app), app


@pytest.fixture
def authenticated_app_client() -> Generator[tuple[TestClient, _FakeClient], None, None]:
    """App with OAuth dependency bypassed and a fake storage client."""
    fake = _FakeClient()
    client, app = _make_authenticated_app(fake)
    yield client, fake
    app.dependency_overrides.clear()


# -----------------------------
# Auth guard
# -----------------------------
def test_storage_list_requires_session_when_not_overridden() -> None:
    """Without OAuth completion, storage routes return 401."""
    client = TestClient(create_app())
    response = client.get("/storage/files/list?container=my-bucket")
    assert response.status_code == 401


# -----------------------------
# list_files
# -----------------------------
def test_storage_list_returns_json_names(
    authenticated_app_client: tuple[TestClient, _FakeClient],
) -> None:
    client, _ = authenticated_app_client
    response = client.get("/storage/files/list?container=my-bucket")
    assert response.status_code == 200
    names = [obj["object_name"] for obj in response.json()]
    assert names == ["a.txt", "b.txt"]


# -----------------------------
# download_file
# -----------------------------
def test_storage_download_returns_bytes(
    authenticated_app_client: tuple[TestClient, _FakeClient],
) -> None:
    client, _ = authenticated_app_client
    response = client.get("/storage/files/download?container=my-bucket&object_name=folder/file.bin")
    assert response.status_code == 200
    assert response.content == b"payload"


# -----------------------------
# upload_obj
# -----------------------------
def test_storage_upload_forwards_body(
    authenticated_app_client: tuple[TestClient, _FakeClient],
) -> None:
    client, fake = authenticated_app_client
    response = client.post(
        "/storage/files/upload?container=my-bucket&remote_path=path/to/obj",
        files={"file": ("obj", BytesIO(b"hello"), "application/octet-stream")},
    )
    assert response.status_code == 201
    assert fake.last_upload is not None
    assert fake.last_upload[0] == "my-bucket"
    assert fake.last_upload[2] == "path/to/obj"


# -----------------------------
# delete_file
# -----------------------------
def test_storage_delete_returns_flag(
    authenticated_app_client: tuple[TestClient, _FakeClient],
) -> None:
    client, _ = authenticated_app_client
    response = client.delete("/storage/files/delete?container=my-bucket&object_name=x")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


# -----------------------------
# get_file_info
# -----------------------------
def test_storage_get_file_info(
    authenticated_app_client: tuple[TestClient, _FakeClient],
) -> None:
    client, _ = authenticated_app_client
    response = client.get("/storage/files/info?container=my-bucket&object_name=file.txt")
    assert response.status_code == 200
    assert response.json()["object_name"] == "file.txt"


# -----------------------------
# Error mapping — ObjectNotFoundError
# -----------------------------
class _NotFoundClient(CloudStorageClient):
    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def upload_obj(self, container: str, file_obj: object, remote_path: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        raise ObjectNotFoundError(_MSG_NO_BUCKET)


@pytest.fixture
def client_with_not_found() -> Generator[TestClient, None, None]:
    tc, app = _make_authenticated_app(_NotFoundClient())
    yield tc
    app.dependency_overrides.clear()


def test_storage_list_maps_object_not_found(client_with_not_found: TestClient) -> None:
    response = client_with_not_found.get("/storage/files/list?container=missing")
    assert response.status_code == 404


# -----------------------------
# Error mapping — StorageBackendError
# -----------------------------
class _FailingDownloadClient(CloudStorageClient):
    def upload_file(self, container: str, local_path: str, remote_path: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def upload_obj(self, container: str, file_obj: object, remote_path: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def list_files(self, container: str, prefix: str) -> list[ObjectInfo]:
        return []

    def delete_file(self, container: str, object_name: str) -> DeleteResult:
        return DeleteResult(deleted=True, version_id=None, request_charged=None)

    def get_file_info(self, container: str, object_name: str) -> ObjectInfo:
        return ObjectInfo(object_name="")

    def download_file(self, container: str, object_name: str, file_name: str) -> ObjectInfo:
        raise StorageBackendError(_MSG_S3_DOWN)


@pytest.fixture
def client_with_failed_download() -> Generator[TestClient, None, None]:
    tc, app = _make_authenticated_app(_FailingDownloadClient())
    yield tc
    app.dependency_overrides.clear()


def test_storage_download_maps_storage_backend_error(client_with_failed_download: TestClient) -> None:
    response = client_with_failed_download.get("/storage/files/download?container=b&object_name=file.txt")
    assert response.status_code == 502
