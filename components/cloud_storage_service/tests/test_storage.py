"""Tests for storage endpoints."""

from __future__ import annotations

from collections.abc import Generator  # noqa: TC003

import pytest
from cloud_storage_client_api.client import Client
from cloud_storage_service.app import create_app
from cloud_storage_service.deps import require_oauth_session
from fastapi.testclient import TestClient
from s3_client_impl.token_store import TokenData, store_token

pytestmark = pytest.mark.unit


class _FakeClient(Client):
    """Minimal fake used only to assert routing and DI wiring."""

    def __init__(self) -> None:
        self.last_upload: tuple[str, str, bytes] | None = None

    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        self.last_upload = (container_name, object_name, data)

    def download_object(self, _container_name: str, _object_name: str) -> bytes:
        return b"payload"

    def delete_object(self, _container_name: str, _object_name: str) -> bool:
        return True

    def list_objects(self, _container_name: str) -> Generator[str, None, None]:
        yield from ["a.txt", "b.txt"]


@pytest.fixture
def authenticated_app_client(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[TestClient, _FakeClient], None, None]:
    """App with OAuth dependency bypassed and a fake storage client."""
    fake = _FakeClient()
    monkeypatch.setattr("cloud_storage_service.routes.storage.get_client", lambda: fake)

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
