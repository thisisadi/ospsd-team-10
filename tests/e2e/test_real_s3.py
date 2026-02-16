import os
import uuid

import pytest
from cloud_storage_client_api.client import get_client


@pytest.mark.e2e
@pytest.mark.aws_credentials
def test_real_s3_flow() -> None:
    """End-to-end S3 flow using real AWS credentials."""
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        pytest.skip("AWS credentials not configured")

    client = get_client()

    container = "test-bucket"  # or use env-configured bucket
    object_name = f"test-object-{uuid.uuid4()}.txt"
    data = b"hello world"

    try:
        # upload
        client.upload_object(container, object_name, data)

        # list
        objects = list(client.list_objects(container))
        assert object_name in objects

        # download
        downloaded = client.download_object(container, object_name)
        assert downloaded == data

    finally:
        # delete remote object
        try:
            client.delete_object(container, object_name)
        except Exception:  # noqa: BLE001
            pass
