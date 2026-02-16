import pytest
from cloud_storage_client_api.client import Client, get_client
from s3_client_impl.client import S3CloudStorageClient


@pytest.mark.integration
def test_get_client_returns_aws_impl() -> None:
    """Verify DI returns AWS implementation."""
    client = get_client()

    # Ensure correct concrete type
    assert isinstance(client, S3CloudStorageClient)

    # Also ensure it satisfies the interface
    assert isinstance(client, Client)
