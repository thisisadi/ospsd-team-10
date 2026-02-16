"""AWS S3 implementation package for the cloud storage client API."""

from __future__ import annotations

from cloud_storage_client_api.client import register_client_factory

from s3_client_impl.client import S3CloudStorageClient

register_client_factory(S3CloudStorageClient)
