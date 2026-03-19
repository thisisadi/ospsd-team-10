import os
import uuid

import pytest
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient
from vertical_api.client import Client, get_client, register_client_factory
from vertical_impl.client import S3CloudStorageClient


def _run_shared_storage_flow(client: Client, container: str) -> None:
    """Run the shared upload, list, download, and delete smoke flow."""
    object_name = f"test-object-{uuid.uuid4()}.txt"
    data = b"hello world"
    try:
        upload_out = client.upload_object(container, object_name, data)
        if hasattr(upload_out, "success"):
            assert upload_out.success is True

        objects = list(client.list_objects(container))
        assert object_name in objects

        downloaded = client.download_object(container, object_name)
        assert downloaded == data
    finally:
        try:
            client.delete_object(container, object_name)
        except Exception:  # noqa: BLE001
            pass


@pytest.mark.e2e
@pytest.mark.aws_credentials
def test_real_s3_flow() -> None:
    """End-to-end S3 flow using real AWS credentials (local implementation)."""
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        pytest.skip("AWS credentials not configured")

    register_client_factory(S3CloudStorageClient)
    container = os.environ["AWS_S3_BUCKET"]
    _run_shared_storage_flow(get_client(), container)


@pytest.mark.e2e
def test_remote_adapter_flow_same_consumer_code() -> None:
    """Same consumer flow against the deployed service via the adapter (optional)."""
    base = os.getenv("SERVICE_BASE_URL", "").strip()
    token = os.getenv("INTEGRATION_SESSION_TOKEN", "").strip()
    bucket = os.getenv("AWS_S3_BUCKET", "").strip()
    if not base or not token or not bucket:
        pytest.skip("SERVICE_BASE_URL, INTEGRATION_SESSION_TOKEN, and AWS_S3_BUCKET required for remote E2E")

    storage = GeneratedStorageApiClient(base_url=base, cookies={"session": token})
    remote_client: Client = CloudStorageServiceAdapter(storage_api=storage)
    _run_shared_storage_flow(remote_client, bucket)
