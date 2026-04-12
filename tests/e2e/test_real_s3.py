"""E2E smoke tests against real AWS and the deployed service."""

from __future__ import annotations

import os
import uuid
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

import pytest
from cloud_storage_api.models import ObjectInfo
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient
from vertical_impl.client import S3CloudStorageClient

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient


def _run_shared_storage_flow(client: CloudStorageClient, container: str) -> None:
    """Run the shared upload, list, download, and delete smoke flow."""
    object_name = f"test-object-{uuid.uuid4()}.txt"
    data = b"hello world"

    try:
        result = client.upload_obj(container, BytesIO(data), object_name)
        assert isinstance(result, ObjectInfo)
        assert result.object_name == object_name

        files = client.list_files(container, prefix="test-object-")
        names = [f.object_name for f in files]
        assert object_name in names

        tmp_path: Path | None = None
        with NamedTemporaryFile(delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            client.download_file(container, object_name, str(tmp_path))
            with tmp_path.open("rb") as f:
                assert f.read() == data
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

        info = client.get_file_info(container, object_name)
        assert isinstance(info, ObjectInfo)
        assert info.object_name == object_name

    finally:
        try:
            client.delete_file(container, object_name)
        except Exception:  # noqa: BLE001
            pass


@pytest.mark.e2e
@pytest.mark.aws_credentials
def test_real_s3_flow() -> None:
    """End-to-end S3 flow using real AWS credentials (local implementation)."""
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        pytest.skip("AWS credentials not configured")

    container = os.environ["AWS_S3_BUCKET"]
    _run_shared_storage_flow(S3CloudStorageClient(), container)


@pytest.mark.e2e
def test_remote_adapter_flow_same_consumer_code() -> None:
    """Same consumer flow against the deployed service via the adapter."""
    base = os.getenv("SERVICE_BASE_URL", "").strip()
    token = os.getenv("INTEGRATION_SESSION_TOKEN", "").strip()
    bucket = os.getenv("AWS_S3_BUCKET", "").strip()

    if not base or not token or not bucket:
        pytest.skip("SERVICE_BASE_URL, INTEGRATION_SESSION_TOKEN, and AWS_S3_BUCKET required for remote E2E")

    storage = GeneratedStorageApiClient(base_url=base, cookies={"session": token})
    remote_client: CloudStorageClient = CloudStorageServiceAdapter(storage_api=storage)
    _run_shared_storage_flow(remote_client, bucket)
