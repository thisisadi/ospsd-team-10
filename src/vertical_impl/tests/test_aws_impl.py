from unittest.mock import MagicMock

import pytest
import requests
from botocore.exceptions import ClientError
from vertical_api.client import ObjectNotFoundError
from vertical_impl._auth import S3Config
from vertical_impl.client import S3CloudStorageClient
from vertical_impl.oauth import auth_callback

pytestmark = pytest.mark.unit


def _s3_client_error(operation: str, code: str, message: str) -> ClientError:
    """Build a minimal botocore ClientError for unit tests (response shape is intentionally partial)."""
    error_response = {
        "Error": {"Code": code, "Message": message},
        "ResponseMetadata": {"HTTPStatusCode": 500},
    }
    return ClientError(error_response, operation)  # type: ignore[arg-type]


def _make_client(mock_s3: MagicMock) -> S3CloudStorageClient:
    """Create a client with injected mock S3 and config."""
    mock_config = S3Config(bucket="test-bucket", region="us-east-1")
    return S3CloudStorageClient(s3=mock_s3, config=mock_config)


# -----------------------------
# upload_object
# -----------------------------
def test_upload_object_calls_s3() -> None:
    mock_s3 = MagicMock()
    client = _make_client(mock_s3)

    client.upload_object("test-bucket", "file.txt", b"data")

    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="file.txt",
        Body=b"data",
    )


def test_upload_object_uses_default_bucket() -> None:
    """If container_name is empty, config bucket should be used."""
    mock_s3 = MagicMock()
    client = _make_client(mock_s3)

    client.upload_object("", "file.txt", b"data")

    mock_s3.put_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="file.txt",
        Body=b"data",
    )


def test_upload_object_propagates_error() -> None:
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = _s3_client_error("PutObject", "TestError", "Upload failed")

    client = _make_client(mock_s3)

    result = client.upload_object("test-bucket", "file.txt", b"data")

    assert result.success is False
    assert result.object_key == "file.txt"
    assert result.metadata is None
    assert result.error is not None
    assert "Upload failed" in result.error


def test_upload_object_success_with_metadata() -> None:
    mock_s3 = MagicMock()
    mock_s3.put_object.return_value = {"ETag": "abc123"}

    client = _make_client(mock_s3)

    result = client.upload_object("test-bucket", "file.txt", b"data")

    assert result.success is True
    assert result.object_key == "file.txt"
    assert result.metadata is not None
    assert result.metadata["etag"] == "abc123"
    assert result.error is None


# -----------------------------
# download_object
# -----------------------------
def test_download_object_calls_s3() -> None:
    mock_s3 = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"hello"
    mock_s3.get_object.return_value = {"Body": mock_body}

    client = _make_client(mock_s3)

    data = client.download_object("test-bucket", "file.txt")

    assert data == b"hello"
    mock_s3.get_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="file.txt",
    )


def test_download_object_maps_no_such_key() -> None:
    mock_s3 = MagicMock()
    mock_s3.get_object.side_effect = _s3_client_error("GetObject", "NoSuchKey", "missing")
    client = _make_client(mock_s3)

    with pytest.raises(ObjectNotFoundError):
        client.download_object("test-bucket", "missing.txt")


# -----------------------------
# delete_object
# -----------------------------
def test_delete_object_success() -> None:
    mock_s3 = MagicMock()
    client = _make_client(mock_s3)

    result = client.delete_object("test-bucket", "file.txt")

    assert result.success is True
    assert result.object_key == "file.txt"
    assert result.error is None
    mock_s3.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="file.txt",
    )


def test_delete_object_failure() -> None:
    mock_s3 = MagicMock()
    mock_s3.delete_object.side_effect = _s3_client_error("DeleteObject", "TestError", "delete boom")

    client = _make_client(mock_s3)

    result = client.delete_object("test-bucket", "file.txt")

    assert result.success is False
    assert result.object_key == "file.txt"
    assert result.error is not None
    assert "delete boom" in result.error


# -----------------------------
# list_objects (normal case)
# -----------------------------
def test_list_objects_returns_keys() -> None:
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "file1.txt"},
            {"Key": "file2.txt"},
        ],
    }

    client = _make_client(mock_s3)

    files = list(client.list_objects("test-bucket"))

    assert files == ["file1.txt", "file2.txt"]


# -----------------------------
# list_objects (empty bucket)
# -----------------------------
def test_list_objects_empty_bucket() -> None:
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {}

    client = _make_client(mock_s3)

    files = list(client.list_objects("test-bucket"))

    assert files == []


# -----------------------------
# list_objects (invalid contents)
# -----------------------------
def test_list_objects_invalid_contents() -> None:
    """If Contents is not a list, method should yield nothing."""
    mock_s3 = MagicMock()
    mock_s3.list_objects_v2.return_value = {"Contents": "invalid"}

    client = _make_client(mock_s3)

    files = list(client.list_objects("test-bucket"))

    assert files == []


# -----------------------------
# OAuth auth_callback tests
# -----------------------------
@pytest.mark.parametrize("provider_error", ["access_denied", "server_error"])
def test_auth_callback_provider_error(provider_error: str) -> None:
    result = auth_callback(
        session_id="session1",
        code="xyz",
        state="abc",
        provider_error=provider_error,
    )

    assert result.success is False
    assert result.token_data is None
    assert result.error_type == "provider_error"
    assert result.error is not None
    assert provider_error in result.error


def test_auth_callback_missing_code() -> None:
    result = auth_callback(
        session_id="session1",
        code=None,
        state="abc",
    )

    assert result.success is False
    assert result.token_data is None
    assert result.error_type == "client_error"
    assert result.error is not None
    assert "authorization code" in result.error


def test_auth_callback_missing_state() -> None:
    result = auth_callback(
        session_id="session1",
        code="some-code",
        state=None,
    )

    assert result.success is False
    assert result.token_data is None
    assert result.error_type == "client_error"
    assert result.error is not None
    assert "state value" in result.error


def test_auth_callback_invalid_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vertical_impl.oauth.validate_state", lambda _session_id, _state: False)

    result = auth_callback(
        session_id="session1",
        code="abc",
        state="mismatch",
    )

    assert result.success is False
    assert result.token_data is None
    assert result.error_type == "csrf_error"
    assert result.error is not None
    assert "CSRF" in result.error


def test_auth_callback_exchange_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("vertical_impl.oauth.validate_state", lambda _session_id, _state: True)
    monkeypatch.setattr(
        "vertical_impl.oauth.exchange_code_for_token",
        lambda _code: (_ for _ in ()).throw(requests.RequestException("exchange boom")),
    )

    result = auth_callback(
        session_id="session1",
        code="abc",
        state="abc",
    )

    assert result.success is False
    assert result.token_data is None
    assert result.error_type == "exchange_error"
    assert result.error is not None
    assert "Failed to exchange" in result.error


def test_auth_callback_success(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_token = object()
    monkeypatch.setattr("vertical_impl.oauth.validate_state", lambda _session_id, _state: True)
    monkeypatch.setattr("vertical_impl.oauth.exchange_code_for_token", lambda _code: dummy_token)

    result = auth_callback(
        session_id="session1",
        code="aaa",
        state="aaa",
    )

    assert result.success is True
    assert result.token_data is dummy_token
    assert result.error_type is None
    assert result.error is None
