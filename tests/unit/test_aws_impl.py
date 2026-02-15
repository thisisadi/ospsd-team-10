from unittest.mock import MagicMock, patch

from cloud_storage_client_aws_impl.client import S3CloudStorageClient


@patch("cloud_storage_client_aws_impl.client.boto3.client")
def test_upload_file_calls_s3(mock_boto_client):
    mock_s3 = MagicMock()
    mock_boto_client.return_value = mock_s3

    client = S3CloudStorageClient(bucket_name="test-bucket")

    client.upload_file("local.txt", "remote.txt")

    mock_s3.upload_file.assert_called_once_with(
        "local.txt", "test-bucket", "remote.txt"
    )
