import pytest
from vertical_adapter.adapter import CloudStorageServiceAdapter
from vertical_api.client import Client, get_client, register_client_factory
from vertical_impl.client import S3CloudStorageClient

from vertical_adapter import register as register_adapter


@pytest.mark.integration
def test_get_client_returns_aws_impl() -> None:
    """Verify DI returns AWS implementation."""
    register_client_factory(S3CloudStorageClient)
    client = get_client()

    # Ensure correct concrete type
    assert isinstance(client, S3CloudStorageClient)

    # Also ensure it satisfies the interface
    assert isinstance(client, Client)


@pytest.mark.integration
def test_adapter_register_exposes_remote_client() -> None:
    """Calling vertical_adapter.register() should wire get_client() to the HTTP adapter."""
    register_client_factory(S3CloudStorageClient)
    assert isinstance(get_client(), S3CloudStorageClient)
    register_adapter()
    assert isinstance(get_client(), CloudStorageServiceAdapter)
    register_client_factory(S3CloudStorageClient)
