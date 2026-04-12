"""Unit tests for the AWS S3 cloud storage client implementation."""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING, Any, TypedDict, cast
from unittest.mock import MagicMock

import pytest
import requests
from botocore.exceptions import ClientError
from cloud_storage_api.exceptions import ObjectNotFoundError, StorageBackendError
from cloud_storage_api.models import ObjectInfo
from vertical_impl._auth import S3Config
from vertical_impl.client import S3CloudStorageClient
from vertical_impl.oauth import auth_callback

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


class _ErrorDict(TypedDict):
    Code: str
    Message: str


class _ClientErrorResponse(TypedDict):
    Error: _ErrorDict
    ResponseMetadata: dict[str, int]


def _s3_client_error(operation: str, code: str, message: str) -> ClientError:
    error_response: _ClientErrorResponse = {
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"HTTPStatusCode": 500},
    }
    return ClientError(cast("Any", error_response), operation)


def _make_client(mock_s3: MagicMock) -> S3CloudStorageClient:
    mock_config = S3Config(bucket="test-bucket", region="us-east-1")
    return S3CloudStorageClient(s3=mock_s3, config=mock_config)


def _mock_head(_key: str = "file.txt", size: int = 4) -> dict[str, Any]:
    """Return a minimal HeadObject response."""
    return {
        "ContentLength": size,
        "ContentType": "application/octet-stream",
        "ETag": "abc123",
        "StorageClass": "STANDARD",
    }


# -----------------------------
# upload_file (from local path)
# -----------------------------
def test_upload_file_calls_s3(tmp_path: Path) -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head()
    client = _make_client(mock_s3)

    local = tmp_path / "file.txt"
    local.write_bytes(b"data")

    result = client.upload_file("test-bucket", str(local), "file.txt")

    mock_s3.put_object.assert_called_once_with(Bucket="test-bucket", Key="file.txt", Body=b"data")
    assert isinstance(result, ObjectInfo)
    assert result.object_name == "file.txt"


def test_upload_file_returns_object_info(tmp_path: Path) -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head(size=100)
    client = _make_client(mock_s3)

    local = tmp_path / "file.txt"
    local.write_bytes(b"x" * 100)

    result = client.upload_file("test-bucket", str(local), "file.txt")

    assert result.integrity == "abc123"
    assert result.size_bytes == 100


def test_upload_file_raises_on_s3_error(tmp_path: Path) -> None:
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = _s3_client_error("PutObject", "TestError", "Upload failed")
    client = _make_client(mock_s3)

    local = tmp_path / "file.txt"
    local.write_bytes(b"data")

    with pytest.raises(StorageBackendError):
        client.upload_file("test-bucket", str(local), "file.txt")


# -----------------------------
# upload_obj (from file-like)
# -----------------------------
def test_upload_obj_calls_s3() -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head()
    client = _make_client(mock_s3)

    result = client.upload_obj("test-bucket", BytesIO(b"data"), "file.txt")

    mock_s3.upload_fileobj.assert_called_once()
    assert isinstance(result, ObjectInfo)
    assert result.object_name == "file.txt"


def test_upload_obj_raises_on_s3_error() -> None:
    mock_s3 = MagicMock()
    mock_s3.upload_fileobj.side_effect = _s3_client_error("PutObject", "TestError", "Upload failed")
    client = _make_client(mock_s3)

    with pytest.raises(StorageBackendError):
        client.upload_obj("test-bucket", BytesIO(b"data"), "file.txt")


# -----------------------------
# download_file
# -----------------------------
def test_download_file_calls_s3(tmp_path: Path) -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head()
    client = _make_client(mock_s3)

    dest = str(tmp_path / "out.txt")
    result = client.download_file("test-bucket", "file.txt", dest)

    mock_s3.download_file.assert_called_once_with("test-bucket", "file.txt", dest)
    assert isinstance(result, ObjectInfo)
    assert result.object_name == "file.txt"


def test_download_file_maps_no_such_key(tmp_path: Path) -> None:
    mock_s3 = MagicMock()
    mock_s3.download_file.side_effect = _s3_client_error("GetObject", "NoSuchKey", "missing")
    client = _make_client(mock_s3)

    with pytest.raises(ObjectNotFoundError):
        client.download_file("test-bucket", "missing.txt", str(tmp_path / "out.txt"))


# -----------------------------
# delete_file
# -----------------------------
def test_delete_file_success() -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head()
    mock_s3.delete_object.return_value = {}
    client = _make_client(mock_s3)

    result = client.delete_file("test-bucket", "file.txt")

    assert result["deleted"] is True
    assert result["version_id"] is None
    mock_s3.delete_object.assert_called_once_with(Bucket="test-bucket", Key="file.txt")


def test_delete_file_raises_object_not_found() -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = _s3_client_error("HeadObject", "NoSuchKey", "missing")
    client = _make_client(mock_s3)

    with pytest.raises(ObjectNotFoundError):
        client.delete_file("test-bucket", "missing.txt")


def test_delete_file_raises_on_s3_error() -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head()
    mock_s3.delete_object.side_effect = _s3_client_error("DeleteObject", "TestError", "delete boom")
    client = _make_client(mock_s3)

    with pytest.raises(StorageBackendError):
        client.delete_file("test-bucket", "file.txt")


# -----------------------------
# list_files
# -----------------------------
def test_list_files_returns_object_infos() -> None:
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "file1.txt", "Size": 10, "ETag": "e1", "StorageClass": "STANDARD"},
            {"Key": "file2.txt", "Size": 20, "ETag": "e2", "StorageClass": "STANDARD"},
        ]
    }
    client = _make_client(mock_s3)

    results = client.list_files("test-bucket", prefix="")

    assert len(results) == 2
    assert all(isinstance(r, ObjectInfo) for r in results)
    assert results[0].object_name == "file1.txt"
    assert results[1].object_name == "file2.txt"


def test_list_files_sorted() -> None:
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "b.txt", "Size": 1},
            {"Key": "a.txt", "Size": 1},
        ]
    }
    client = _make_client(mock_s3)

    results = client.list_files("test-bucket", prefix="")
    assert [r.object_name for r in results] == ["a.txt", "b.txt"]


def test_list_files_empty_bucket() -> None:
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {}
    client = _make_client(mock_s3)

    assert client.list_files("test-bucket", prefix="") == []


def test_list_files_invalid_contents() -> None:
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {"Contents": "invalid"}
    client = _make_client(mock_s3)

    assert client.list_files("test-bucket", prefix="") == []


# -----------------------------
# get_file_info
# -----------------------------
def test_get_file_info_returns_object_info() -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.return_value = _mock_head(size=42)
    client = _make_client(mock_s3)

    result = client.get_file_info("test-bucket", "file.txt")

    mock_s3.head_object.assert_called_once_with(Bucket="test-bucket", Key="file.txt")
    assert isinstance(result, ObjectInfo)
    assert result.object_name == "file.txt"
    assert result.size_bytes == 42


def test_get_file_info_raises_object_not_found() -> None:
    mock_s3 = MagicMock()
    mock_s3.head_object.side_effect = _s3_client_error("HeadObject", "NoSuchKey", "missing")
    client = _make_client(mock_s3)

    with pytest.raises(ObjectNotFoundError):
        client.get_file_info("test-bucket", "missing.txt")


# -----------------------------
# OAuth auth_callback tests
# -----------------------------
@pytest.mark.parametrize("provider_error", ["access_denied", "server_error"])
def test_auth_callback_provider_error(provider_error: str) -> None:
    result = auth_callback(session_id="session1", code="xyz", state="abc", provider_error=provider_error)
    assert result.success is False
    assert result.token_data is None
    assert result.error_type == "provider_error"
    assert isinstance(result.error, str)
    assert provider_error in result.error


def test_auth_callback_missing_code() -> None:
    result = auth_callback(session_id="session1", code=None, state="abc")
    assert result.success is False
    assert result.error_type == "client_error"
    assert isinstance(result.error, str)
    assert "authorization code" in result.error


def test_auth_callback_missing_state() -> None:
    result = auth_callback(session_id="session1", code="some-code", state=None)
    assert result.success is False
    assert result.error_type == "client_error"
    assert isinstance(result.error, str)
    assert "state value" in result.error


def test_auth_callback_invalid_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vertical_impl.oauth.validate_state", lambda _s, _st: False)
    result = auth_callback(session_id="session1", code="abc", state="mismatch")
    assert result.success is False
    assert result.error_type == "csrf_error"
    assert isinstance(result.error, str)
    assert "CSRF" in result.error


def test_auth_callback_exchange_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vertical_impl.oauth.validate_state", lambda _s, _st: True)
    monkeypatch.setattr(
        "vertical_impl.oauth.exchange_code_for_token",
        lambda _code: (_ for _ in ()).throw(requests.RequestException("exchange boom")),
    )
    result = auth_callback(session_id="session1", code="abc", state="abc")
    assert result.success is False
    assert result.error_type == "exchange_error"
    assert isinstance(result.error, str)
    assert "Failed to exchange" in result.error


def test_auth_callback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_token = object()
    monkeypatch.setattr("vertical_impl.oauth.validate_state", lambda _s, _st: True)
    monkeypatch.setattr("vertical_impl.oauth.exchange_code_for_token", lambda _code: dummy_token)
    result = auth_callback(session_id="session1", code="aaa", state="aaa")
    assert result.success is True
    assert result.token_data is dummy_token
    assert result.error_type is None
