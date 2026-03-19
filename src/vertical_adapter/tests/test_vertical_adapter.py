"""Unit tests for CloudStorageServiceAdapter delegation."""

from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient
from vertical_api.client import DeleteResult, NotAuthenticatedError, ObjectNotFoundError, StorageOperationFailedError
from vertical_service_api_client.models.http_validation_error import HTTPValidationError

from vertical_service_api_client import errors as api_errors

pytestmark = pytest.mark.unit


def _mock_response(*, status: HTTPStatus, parsed: object | None = None, content: bytes = b"") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.parsed = parsed
    r.content = content
    return r


def test_adapter_delegates_upload() -> None:
    storage_api = MagicMock()
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.upload_object("bucket", "file.txt", b"abc")

    storage_api.upload_object.assert_called_once_with("bucket", "file.txt", b"abc")
    assert result.success is True
    assert result.object_key == "file.txt"
    assert result.container_name == "bucket"


def test_adapter_delegates_download() -> None:
    storage_api = MagicMock()
    storage_api.download_object.return_value = b"content"
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.download_object("bucket", "file.txt")

    assert result == b"content"
    storage_api.download_object.assert_called_once_with("bucket", "file.txt")


def test_adapter_delegates_delete() -> None:
    storage_api = MagicMock()
    storage_api.delete_object.return_value = DeleteResult(success=True, object_key="file.txt")
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.delete_object("bucket", "file.txt")

    assert result.success is True
    assert result.object_key == "file.txt"
    storage_api.delete_object.assert_called_once_with("bucket", "file.txt")


def test_adapter_delegates_list() -> None:
    storage_api = MagicMock()
    storage_api.list_objects.return_value = ["a", "b"]
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = list(adapter.list_objects("bucket"))

    assert result == ["a", "b"]
    storage_api.list_objects.assert_called_once_with("bucket")


def test_generated_upload_maps_unexpected_401(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(**_kwargs: object) -> None:
        raise api_errors.UnexpectedStatus(401, b"")

    monkeypatch.setattr("vertical_adapter.adapter.upload_object_api.sync_detailed", _raise)
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(NotAuthenticatedError):
        client.upload_object("b", "k", b"x")


def test_generated_download_maps_unexpected_404(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(**_kwargs: object) -> None:
        raise api_errors.UnexpectedStatus(404, b"")

    monkeypatch.setattr("vertical_adapter.adapter.download_object_api.sync_detailed", _raise)
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(ObjectNotFoundError):
        client.download_object("b", "k")


def test_generated_upload_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = HTTPValidationError()
    monkeypatch.setattr(
        "vertical_adapter.adapter.upload_object_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.CREATED, parsed=bad),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(StorageOperationFailedError):
        client.upload_object("b", "k", b"x")


def test_generated_upload_bad_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.upload_object_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.BAD_GATEWAY, parsed=None),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(StorageOperationFailedError):
        client.upload_object("b", "k", b"x")


def test_generated_list_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.list_objects_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.OK, parsed=["one", "two"]),
    )
    client = GeneratedStorageApiClient("http://example.test")
    assert client.list_objects("bucket") == ["one", "two"]


def test_generated_delete_maps_deleted_false(monkeypatch: pytest.MonkeyPatch) -> None:
    class _DeletePayload:
        def __getitem__(self, key: str) -> bool:
            if key == "deleted":
                return False
            raise KeyError(key)

    monkeypatch.setattr(
        "vertical_adapter.adapter.delete_object_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.OK, parsed=_DeletePayload()),
    )
    client = GeneratedStorageApiClient("http://example.test")
    out = client.delete_object("b", "k")
    assert out.success is False
    assert out.object_key == "k"
