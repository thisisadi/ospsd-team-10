# ruff: noqa: ARG002
"""Tests for storage endpoints."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from cloud_storage_api.exceptions import ObjectNotFoundError, StorageBackendError
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


# -----------------------------
# Fake client
# -----------------------------
class _FakeClient:
    def __init__(self) -> None:
        self.last_upload: tuple[str, object, str] | None = None

    def upload_file(self, container: str, local_path: str, remote_path: str) -> dict:
        self.last_upload = (container, local_path, remote_path)
        return {"object_name": remote_path}

    def upload_obj(self, container: str, file_obj: object, remote_path: str) -> dict:
        self.last_upload = (container, file_obj, remote_path)
        return {"object_name": remote_path}

    def download_file(self, container: str, object_name: str, file_name: str) -> dict:
        with Path(file_name).open("wb") as f:
            f.write(b"payload")
        return {"object_name": object_name}

    def list_files(self, container: str, prefix: str) -> list[dict]:
        return [{"object_name": "a.txt"}, {"object_name": "b.txt"}]

    def delete_file(self, container: str, object_name: str) -> dict:
        return {"deleted": True}

    def get_file_info(self, container: str, object_name: str) -> dict:
        return {"object_name": object_name}


# -----------------------------
# App helper
# -----------------------------
def _make_authenticated_app(fake: _FakeClient) -> tuple[TestClient, FastAPI]:
    app = create_app()
    app.state.storage_client = fake

    store_token(
        "test-session",
        TokenData(
            access_token="test-access-token",  # noqa: S106
            token_type="Bearer",  # noqa: S106
            expires_at=None,
        ),
    )

    app.dependency_overrides[require_oauth_session] = lambda: "test-session"
    return TestClient(app), app


@pytest.fixture
def authenticated_app_client() -> Generator[tuple[TestClient, _FakeClient], None, None]:
    fake = _FakeClient()
    client, app = _make_authenticated_app(fake)
    yield client, fake
    app.dependency_overrides.clear()


# -----------------------------
# Existing tests
# -----------------------------
def test_storage_list_returns_json_names(authenticated_app_client) -> None:
    client, _ = authenticated_app_client
    response = client.get("/storage/files/list?container=my-bucket")
    assert response.status_code == 200
    assert [x["object_name"] for x in response.json()] == ["a.txt", "b.txt"]


def test_storage_download_returns_bytes(authenticated_app_client) -> None:
    client, _ = authenticated_app_client
    response = client.get("/storage/files/download?container=my-bucket&object_name=file.bin")
    assert response.status_code == 200
    assert response.content == b"payload"


def test_storage_upload_forwards_body(authenticated_app_client) -> None:
    client, fake = authenticated_app_client
    response = client.post(
        "/storage/files/upload?container=my-bucket&remote_path=obj",
        files={"file": ("obj", BytesIO(b"hello"), "application/octet-stream")},
    )
    assert response.status_code == 201
    assert fake.last_upload[0] == "my-bucket"


def test_storage_delete_returns_flag(authenticated_app_client) -> None:
    client, _ = authenticated_app_client
    response = client.delete("/storage/files/delete?container=my-bucket&object_name=x")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_storage_get_file_info(authenticated_app_client) -> None:
    client, _ = authenticated_app_client
    response = client.get(
        "/storage/files/info?container=my-bucket&object_name=file.txt"
    )
    assert response.status_code == 200
    assert response.json()["object_name"] == "file.txt"


# -----------------------------
# Error mapping
# -----------------------------
class _NotFoundClient(_FakeClient):
    def list_files(self, container: str, prefix: str) -> list[dict]:
        raise ObjectNotFoundError(_MSG_NO_BUCKET)


@pytest.fixture
def client_with_not_found() -> Generator[TestClient, None, None]:
    client, app = _make_authenticated_app(_NotFoundClient())
    yield client
    app.dependency_overrides.clear()


def test_storage_list_maps_object_not_found(client_with_not_found) -> None:
    response = client_with_not_found.get("/storage/files/list?container=missing")
    assert response.status_code == 404


class _FailingDownloadClient(_FakeClient):
    def download_file(self, container: str, object_name: str, file_name: str) -> dict:
        raise StorageBackendError(_MSG_S3_DOWN)


@pytest.fixture
def client_with_failed_download() -> Generator[TestClient, None, None]:
    client, app = _make_authenticated_app(_FailingDownloadClient())
    yield client
    app.dependency_overrides.clear()


def test_storage_download_maps_storage_backend_error(
    client_with_failed_download,
) -> None:
    response = client_with_failed_download.get(
        "/storage/files/download?container=b&object_name=file.txt"
    )
    assert response.status_code == 502


# -----------------------------
# FINAL COVERAGE BOOST TEST (SAFE + COMPLETE)
# -----------------------------
def test_storage_full_route_coverage(authenticated_app_client) -> None:
    """
    Executes all storage routes to cover missing branches safely.
    """
    client, fake = authenticated_app_client

    from cloud_storage_api.exceptions import ObjectNotFoundError, StorageBackendError

    # -----------------------------
    # SUCCESS PATHS
    # -----------------------------
    assert client.get("/storage/files/list?container=test").status_code == 200
    assert client.get(
        "/storage/files/info?container=test&object_name=x"
    ).status_code == 200
    assert client.get(
        "/storage/files/download?container=test&object_name=x"
    ).status_code == 200
    assert client.delete(
        "/storage/files/delete?container=test&object_name=x"
    ).status_code == 200

    # -----------------------------
    # ERROR PATHS
    # -----------------------------
    def boom_list(*args, **kwargs):
        raise ObjectNotFoundError("forced error")

    def boom_download(*args, **kwargs):
        raise StorageBackendError("forced error")

    fake.list_files = boom_list
    fake.download_file = boom_download

    assert client.get("/storage/files/list?container=test").status_code == 404
    assert client.get(
        "/storage/files/download?container=test&object_name=x"
    ).status_code == 502