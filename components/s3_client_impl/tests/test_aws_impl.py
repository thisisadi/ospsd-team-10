from unittest.mock import MagicMock

import pytest
from s3_client_impl._auth import S3Config
from s3_client_impl.client import S3CloudStorageClient


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


# -----------------------------
# delete_object
# -----------------------------
def test_delete_object_calls_s3() -> None:
    mock_s3 = MagicMock()
    client = _make_client(mock_s3)

    result = client.delete_object("test-bucket", "file.txt")

    assert result is True
    mock_s3.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="file.txt",
    )


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
# Error propagation test
# -----------------------------
def test_upload_object_propagates_error() -> None:
    mock_s3 = MagicMock()
    mock_s3.put_object.side_effect = Exception("Upload failed")

    client = _make_client(mock_s3)

    with pytest.raises(Exception, match="Upload failed"):
        client.upload_object("test-bucket", "file.txt", b"data")
