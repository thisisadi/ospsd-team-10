"""Unit tests for CloudStorageServiceAdapter delegation."""

from __future__ import annotations

from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ObjectNotFoundError,
    StorageBackendError,
)
from cloud_storage_api.models import DeleteResult, ObjectInfo
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient
from vertical_service_api_client.models.http_validation_error import HTTPValidationError

from vertical_service_api_client import errors as api_errors

pytestmark = pytest.mark.unit


def _mock_response(*, status: HTTPStatus, parsed: object | None = None, content: bytes = b"") -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.parsed = parsed
    r.content = content
    return r


_FAKE_INFO = ObjectInfo(object_name="file.txt", size_bytes=3, integrity="etag")


# -----------------------------
# Adapter delegation
# -----------------------------
def test_adapter_delegates_upload_obj() -> None:
    storage_api = MagicMock()
    storage_api.upload_obj.return_value = _FAKE_INFO
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.upload_obj("bucket", BytesIO(b"abc"), "file.txt")

    assert storage_api.upload_obj.call_count == 1
    call_args = storage_api.upload_obj.call_args[0]
    assert call_args[0] == "bucket"
    assert call_args[2] == "file.txt"
    assert isinstance(result, ObjectInfo)
    assert result.object_name == "file.txt"


def test_adapter_delegates_upload_file(tmp_path: Path) -> None:
    local = tmp_path / "file.txt"
    local.write_bytes(b"abc")
    storage_api = MagicMock()
    storage_api.upload_obj.return_value = _FAKE_INFO
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.upload_file("bucket", str(local), "file.txt")

    storage_api.upload_obj.assert_called_once()
    assert isinstance(result, ObjectInfo)


def test_adapter_delegates_download(tmp_path: Path) -> None:
    storage_api = MagicMock()
    storage_api.download_file.return_value = b"content"
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    dest = str(tmp_path / "out.txt")
    result = adapter.download_file("bucket", "file.txt", dest)

    storage_api.download_file.assert_called_once_with("bucket", "file.txt")
    assert isinstance(result, ObjectInfo)
    assert result.size_bytes == 7
    with Path(dest).open("rb") as f:
        assert f.read() == b"content"


def test_adapter_delegates_delete() -> None:
    storage_api = MagicMock()
    storage_api.delete_file.return_value = DeleteResult(deleted=True, version_id=None, request_charged=None)
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.delete_file("bucket", "file.txt")

    assert result["deleted"] is True
    storage_api.delete_file.assert_called_once_with("bucket", "file.txt")


def test_adapter_delegates_list() -> None:
    storage_api = MagicMock()
    storage_api.list_files.return_value = [ObjectInfo(object_name="a.txt"), ObjectInfo(object_name="b.txt")]
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.list_files("bucket", prefix="")

    assert [r.object_name for r in result] == ["a.txt", "b.txt"]
    storage_api.list_files.assert_called_once_with("bucket", "")


def test_adapter_delegates_get_file_info() -> None:
    storage_api = MagicMock()
    storage_api.get_file_info.return_value = _FAKE_INFO
    adapter = CloudStorageServiceAdapter(storage_api=storage_api)

    result = adapter.get_file_info("bucket", "file.txt")

    assert result.object_name == "file.txt"
    storage_api.get_file_info.assert_called_once_with("bucket", "file.txt")


# -----------------------------
# GeneratedStorageApiClient — error mapping
# -----------------------------
def test_generated_upload_maps_unexpected_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.upload_file_api.sync_detailed",
        lambda **_k: (_ for _ in ()).throw(api_errors.UnexpectedStatus(401, b"")),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(AuthenticationError):
        client.upload_obj("b", BytesIO(b"x"), "k")


def test_generated_download_maps_unexpected_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.download_file_api.sync_detailed",
        lambda **_k: (_ for _ in ()).throw(api_errors.UnexpectedStatus(404, b"")),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(ObjectNotFoundError):
        client.download_file("b", "k")


def test_generated_upload_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.upload_file_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.CREATED, parsed=HTTPValidationError()),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(StorageBackendError):
        client.upload_obj("b", BytesIO(b"x"), "k")


def test_generated_upload_bad_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.upload_file_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.BAD_GATEWAY),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(StorageBackendError):
        client.upload_obj("b", BytesIO(b"x"), "k")


def test_generated_list_success(monkeypatch: pytest.MonkeyPatch) -> None:
    parsed = [{"object_name": "one"}, {"object_name": "two"}]
    monkeypatch.setattr(
        "vertical_adapter.adapter.list_files_api.sync_detailed",
        lambda **_k: _mock_response(status=HTTPStatus.OK, parsed=parsed),
    )
    client = GeneratedStorageApiClient("http://example.test")
    result = client.list_files("bucket", prefix="")
    assert [r.object_name for r in result] == ["one", "two"]


def test_generated_delete_maps_deleted_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.delete_file_api.sync_detailed",
        lambda **_k: _mock_response(
            status=HTTPStatus.OK,
            parsed={"deleted": False, "version_id": None, "request_charged": None},
        ),
    )
    client = GeneratedStorageApiClient("http://example.test")
    result = client.delete_file("b", "k")
    assert result["deleted"] is False


def test_generated_get_file_info_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.get_file_info_api.sync_detailed",
        lambda **_k: _mock_response(
            status=HTTPStatus.OK,
            parsed={"object_name": "file.txt", "size_bytes": 42},
        ),
    )
    client = GeneratedStorageApiClient("http://example.test")
    result = client.get_file_info("b", "file.txt")
    assert result.object_name == "file.txt"
    assert result.size_bytes == 42


def test_generated_get_file_info_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "vertical_adapter.adapter.get_file_info_api.sync_detailed",
        lambda **_k: (_ for _ in ()).throw(api_errors.UnexpectedStatus(404, b"")),
    )
    client = GeneratedStorageApiClient("http://example.test")
    with pytest.raises(ObjectNotFoundError):
        client.get_file_info("b", "missing.txt")
