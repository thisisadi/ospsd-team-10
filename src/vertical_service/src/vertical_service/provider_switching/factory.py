"""Factory for selecting cloud storage providers."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from vertical_impl.client import S3CloudStorageClient

from vertical_service.provider_switching.gcp_storage_client import GCPCloudStorageClient
from vertical_service.provider_switching.mock_storage_client import MockCloudStorageClient

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient

_DEFAULT_PROVIDER = "s3"
_VALID_PROVIDERS = {"s3", "gcp", "mock"}


def create_storage_client() -> CloudStorageClient:
    """Create a CloudStorageClient from STORAGE_PROVIDER configuration."""
    provider = os.getenv("STORAGE_PROVIDER", _DEFAULT_PROVIDER).strip().lower()

    if provider == "s3":
        return S3CloudStorageClient()
    if provider == "gcp":
        return GCPCloudStorageClient()
    if provider == "mock":
        return MockCloudStorageClient()

    valid = ", ".join(sorted(_VALID_PROVIDERS))
    msg = f"Invalid STORAGE_PROVIDER='{provider}'. Valid values are: {valid}."
    raise ValueError(msg)
