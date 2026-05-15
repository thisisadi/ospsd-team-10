"""AWS S3 implementation package for the cloud storage client API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vertical_impl.client import S3CloudStorageClient

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient


def factory() -> CloudStorageClient:
    """Create and return a new S3CloudStorageClient instance."""
    return S3CloudStorageClient()
