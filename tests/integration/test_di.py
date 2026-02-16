import pytest
from cloud_storage_client_api.client import get_client
from cloud_storage_client_aws_impl.client import S3CloudStorageClient


@pytest.mark.integration
def test_get_client_returns_aws_impl():
    """Verify DI returns AWS implementation."""
    client = get_client()

    assert isinstance(client, S3CloudStorageClient)
