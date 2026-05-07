"""Integration tests for provider switching via CloudStorageClient interface."""

from __future__ import annotations

import os
import uuid

import pytest
from cloud_storage_api import CloudStorageClient
from cloud_storage_api.exceptions import ObjectNotFoundError
from cloud_storage_api.models import ObjectInfo
from vertical_impl.client import S3CloudStorageClient
from vertical_service.provider_switching.demo_workflow import run_storage_workflow
from vertical_service.provider_switching.factory import create_storage_client
from vertical_service.provider_switching.mock_storage_client import MockCloudStorageClient


@pytest.mark.integration
def test_factory_returns_mock_for_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")
    client = create_storage_client()
    assert isinstance(client, MockCloudStorageClient)
    assert isinstance(client, CloudStorageClient)


@pytest.mark.integration
def test_factory_defaults_to_s3_when_provider_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_PROVIDER", raising=False)
    client = create_storage_client()
    assert isinstance(client, S3CloudStorageClient)
    assert isinstance(client, CloudStorageClient)


@pytest.mark.integration
def test_factory_returns_s3_for_s3_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    client = create_storage_client()
    assert isinstance(client, S3CloudStorageClient)
    assert isinstance(client, CloudStorageClient)


@pytest.mark.integration
def test_factory_raises_value_error_for_invalid_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_PROVIDER", "invalid-provider")
    with pytest.raises(ValueError, match="Invalid STORAGE_PROVIDER='invalid-provider'"):
        create_storage_client()


@pytest.mark.integration
def test_shared_workflow_runs_against_mock_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_PROVIDER", "mock")
    client = create_storage_client()

    container = "demo-container"
    object_name = f"demo/{uuid.uuid4()}.txt"
    payload = b"provider switching demo payload"

    result = run_storage_workflow(
        client=client,
        container=container,
        object_name=object_name,
        data=payload,
    )

    upload = result["upload"]
    listed = result["list"]
    info = result["info"]
    download = result["download"]
    delete = result["delete"]

    assert isinstance(upload, ObjectInfo)
    assert upload.object_name == object_name

    assert all(isinstance(item, ObjectInfo) for item in listed)
    assert any(item.object_name == object_name for item in listed)

    assert isinstance(info, ObjectInfo)
    assert info.object_name == object_name

    assert isinstance(download, ObjectInfo)
    assert download.object_name == object_name
    assert result["downloaded_data"] == payload

    assert delete["deleted"] is True

    with pytest.raises(ObjectNotFoundError):
        client.get_file_info(container=container, object_name=object_name)


@pytest.mark.integration
@pytest.mark.aws_credentials
def test_shared_workflow_s3_provider_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    if not os.getenv("AWS_ACCESS_KEY_ID") or not os.getenv("AWS_S3_BUCKET"):
        pytest.skip("AWS credentials and AWS_S3_BUCKET are required for S3 workflow test")

    # This verifies factory wiring for S3 without forcing AWS calls in CI.
    client = create_storage_client()
    assert isinstance(client, S3CloudStorageClient)
