import os
import tempfile

from cloud_storage_client_api.client import get_client


def test_real_s3_flow():
    client = get_client()

    # create temp file
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(b"hello world")
        local_path = tmp.name

    remote_path = "test-file.txt"
    download_path = local_path + "_downloaded"

    # upload
    client.upload_file(local_path, remote_path)

    # list
    files = client.list_files()
    assert remote_path in files

    # download
    client.download_file(remote_path, download_path)
    assert os.path.exists(download_path)

    # delete
    client.delete_file(remote_path)
