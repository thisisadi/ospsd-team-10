"""Tests for storage endpoints."""

from __future__ import annotations

from collections.abc import Generator, Iterator  # noqa: TC003

import pytest
from fastapi.testclient import TestClient
from vertical_api.client import (
    Client,
    DeleteResult,
    ObjectNotFoundError,
    StorageOperationFailedError,
    UploadResult,
)
from vertical_impl.token_store import TokenData, store_token
from vertical_service.app import create_app
from vertical_service.deps import require_oauth_session

pytestmark = pytest.mark.unit

_MSG_NO_BUCKET = "no bucket"
_MSG_S3_DOWN = "s3 down"


class _FakeClient(Client):
    """Minimal fake used only to assert routing and DI wiring."""

    def __init__(self) -> None:
        self.last_upload: tuple[str, str, bytes] | None = None

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> UploadResult:
        self.last_upload = (container_name, object_name, data)
        return UploadResult(
            success=True,
            container_name=container_name,
            object_key=object_name,
        )

    def download_object(self, _container_name: str, _object_name: str) -> bytes:
        return b"payload"

    def delete_object(self, _container_name: str, object_name: str) -> DeleteResult:
        return DeleteResult(success=True, object_key=object_name)

    def list_objects(self, _container_name: str) -> Generator[str, None, None]:
        yield from ["a.txt", "b.txt"]


@pytest.fixture
def authenticated_app_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, _FakeClient], None, None]:
    """App with OAuth dependency bypassed and a fake storage client."""
    fake = _FakeClient()
    monkeypatch.setattr("vertical_service.routes.storage.get_client", lambda: fake)

    app = create_app()
    store_token(
        "test-session",
        TokenData(
            access_token="test-access-token",  # noqa: S106
            token_type="Bearer",  # noqa: S106
            expires_at=None,
        ),
    )
    app.dependency_overrides[require_oauth_session] = lambda: "test-session"
    client = TestClient(app)
    yield client, fake
    app.dependency_overrides.clear()


def test_storage_list_requires_session_when_not_overridden() -> None:
    """Without OAuth completion, storage routes return 401."""
    client = TestClient(create_app())
    response = client.get("/storage/my-bucket/objects")
    assert response.status_code == 401


def test_storage_list_returns_json_names(authenticated_app_client: tuple[TestClient, _FakeClient]) -> None:
    """GET /storage/{container}/objects lists keys via get_client()."""
    client, _fake = authenticated_app_client
    response = client.get("/storage/my-bucket/objects")
    assert response.status_code == 200
    assert response.json() == ["a.txt", "b.txt"]


def test_storage_download_returns_bytes(authenticated_app_client: tuple[TestClient, _FakeClient]) -> None:
    """GET /storage/{container}/objects/{key} returns octet stream."""
    client, _fake = authenticated_app_client
    response = client.get("/storage/my-bucket/objects/folder/file.bin")
    assert response.status_code == 200
    assert response.content == b"payload"


def test_storage_upload_forwards_body(authenticated_app_client: tuple[TestClient, _FakeClient]) -> None:
    """POST uploads raw body to upload_object."""
    client, fake = authenticated_app_client
    response = client.post(
        "/storage/my-bucket/objects/path/to/obj",
        content=b"hello",
        headers={"Content-Type": "application/octet-stream"},
    )
    assert response.status_code == 201
    assert fake.last_upload == ("my-bucket", "path/to/obj", b"hello")


def test_storage_delete_returns_flag(authenticated_app_client: tuple[TestClient, _FakeClient]) -> None:
    """DELETE returns JSON with deleted flag."""
    client, _fake = authenticated_app_client
    response = client.delete("/storage/my-bucket/objects/x")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}


class _NotFoundClient(Client):
    """Client that raises port errors for route mapping tests."""

    def upload_object(self, *_a: object, **_k: object) -> UploadResult:
        return UploadResult(success=True, container_name="", object_key="")

    def download_object(self, *_a: object, **_k: object) -> bytes:
        return b""

    def delete_object(self, *_a: object, **_k: object) -> DeleteResult:
        return DeleteResult(success=True, object_key="")

    def list_objects(self, _container_name: str) -> Iterator[str]:
        raise ObjectNotFoundError(_MSG_NO_BUCKET)


@pytest.fixture
def client_with_not_found(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    """App wired to a client that raises ObjectNotFoundError on list."""

    def _factory() -> _NotFoundClient:
        return _NotFoundClient()

    monkeypatch.setattr("vertical_service.routes.storage.get_client", _factory)
    app = create_app()
    store_token(
        "test-session",
        TokenData(
            access_token="test-access-token",  # noqa: S106
            token_type="Bearer",  # noqa: S106
            expires_at=None,
        ),
    )
    app.dependency_overrides[require_oauth_session] = lambda: "test-session"
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.clear()


def test_storage_list_maps_object_not_found(client_with_not_found: TestClient) -> None:
    """ObjectNotFoundError from the impl should become HTTP 404."""
    response = client_with_not_found.get("/storage/missing/objects")
    assert response.status_code == 404


class _FailingDownloadClient(Client):
    def upload_object(self, c: str, o: str, _data: bytes) -> UploadResult:
        return UploadResult(success=True, container_name=c, object_key=o)

    def list_objects(self, _container_name: str) -> Generator[str, None, None]:
        yield from ()

    def delete_object(self, _c: str, o: str) -> DeleteResult:
        return DeleteResult(success=True, object_key=o)

    def download_object(self, *_a: object, **_k: object) -> bytes:
        raise StorageOperationFailedError(_MSG_S3_DOWN)


@pytest.fixture
def client_with_failed_download(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    def _factory() -> _FailingDownloadClient:
        return _FailingDownloadClient()

    monkeypatch.setattr("vertical_service.routes.storage.get_client", _factory)
    app = create_app()
    store_token(
        "test-session",
        TokenData(
            access_token="test-access-token",  # noqa: S106
            token_type="Bearer",  # noqa: S106
            expires_at=None,
        ),
    )
    app.dependency_overrides[require_oauth_session] = lambda: "test-session"
    tc = TestClient(app)
    yield tc
    app.dependency_overrides.clear()


def test_storage_download_maps_storage_operation_failed(client_with_failed_download: TestClient) -> None:
    response = client_with_failed_download.get("/storage/b/objects/file.txt")
    assert response.status_code == 502
