from unittest.mock import MagicMock, patch

import pytest
from cloud_storage_client_aws_impl.client import S3CloudStorageClient

# -----------------------------
# Constructor test
# -----------------------------


@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_constructor_creates_s3_client(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = S3CloudStorageClient(bucket_name="test-bucket")

    assert client.bucket_name == "test-bucket"
    mock_boto_client.assert_called_once_with("s3")


# -----------------------------
# upload_file
# -----------------------------
@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_upload_file_calls_s3(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = S3CloudStorageClient(bucket_name="test-bucket")

    client.upload_file("local.txt", "remote.txt")

    mock_s3.upload_file.assert_called_once_with(
        "local.txt", "test-bucket", "remote.txt",
    )


# -----------------------------
# download_file
# -----------------------------
@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_download_file_calls_s3(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = S3CloudStorageClient(bucket_name="test-bucket")

    client.download_file("remote.txt", "local.txt")

    mock_s3.download_file.assert_called_once_with(
        "test-bucket", "remote.txt", "local.txt",
    )


# -----------------------------
# delete_file
# -----------------------------
@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_delete_file_calls_s3(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = S3CloudStorageClient(bucket_name="test-bucket")

    client.delete_file("remote.txt")

    mock_s3.delete_object.assert_called_once_with(
        Bucket="test-bucket",
        Key="remote.txt",
    )


# -----------------------------
# list_files (normal case)
# -----------------------------
@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_list_files_returns_keys(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    mock_s3.list_objects_v2.return_value = {
        "Contents": [
            {"Key": "file1.txt"},
            {"Key": "file2.txt"},
        ],
    }

    client = S3CloudStorageClient(bucket_name="test-bucket")

    files = client.list_files()

    assert files == ["file1.txt", "file2.txt"]


# -----------------------------
# list_files (empty bucket)
# -----------------------------
@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_list_files_empty_bucket(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    mock_s3.list_objects_v2.return_value = {}

    client = S3CloudStorageClient(bucket_name="test-bucket")

    files = client.list_files()

    assert files == []


# -----------------------------
# Error propagation test
# -----------------------------
@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_upload_file_propagates_error(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    mock_s3.upload_file.side_effect = Exception("Upload failed")

    client = S3CloudStorageClient(bucket_name="test-bucket")

    with pytest.raises(Exception, match="Upload failed"):
        client.upload_file("local.txt", "remote.txt")
