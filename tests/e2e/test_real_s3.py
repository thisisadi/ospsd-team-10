import os
import tempfile
import uuid

import pytest
from cloud_storage_client_api.client import get_client


@pytest.mark.e2e
@pytest.mark.aws_credentials
def test_real_s3_flow():
    # Skip test if AWS credentials are missing
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        pytest.skip("AWS credentials not configured")

    client = get_client()

    # create temp file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"hello world")
        local_path = tmp.name

    # use unique filename to avoid collisions
    remote_path = f"test-file-{uuid.uuid4()}.txt"
    download_path = local_path + "_downloaded"

    try:
        # upload
        client.upload_file(local_path, remote_path)

        # list
        files = client.list_files()
        assert remote_path in files

        # download
        client.download_file(remote_path, download_path)
        assert os.path.exists(download_path)

    finally:
        # delete remote file
        try:
            client.delete_file(remote_path)
        except Exception:  # noqa: BLE001
            pass

        # cleanup local files
        for path in [local_path, download_path]:
            if os.path.exists(path):
                os.remove(path)
