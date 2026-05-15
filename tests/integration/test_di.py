"""DI wiring tests — verify correct concrete types are returned."""

import pytest
from cloud_storage_api import CloudStorageClient
from vertical_adapter.adapter import CloudStorageServiceAdapter
from vertical_impl.client import S3CloudStorageClient


@pytest.mark.integration
def test_impl_satisfies_interface() -> None:
    """Verify S3CloudStorageClient satisfies the shared interface."""
    client = S3CloudStorageClient()
    assert isinstance(client, CloudStorageClient)


@pytest.mark.integration
def test_adapter_satisfies_interface() -> None:
    """Verify CloudStorageServiceAdapter satisfies the shared interface."""
    adapter = CloudStorageServiceAdapter()
    assert isinstance(adapter, CloudStorageClient)
