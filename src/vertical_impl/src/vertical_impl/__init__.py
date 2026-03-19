"""AWS S3 implementation package for the cloud storage client API."""

from __future__ import annotations

from vertical_api.client import register_client_factory

from vertical_impl.client import S3CloudStorageClient

register_client_factory(S3CloudStorageClient)
