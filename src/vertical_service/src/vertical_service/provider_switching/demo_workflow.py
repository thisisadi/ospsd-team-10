"""Shared provider-agnostic workflow for HW3 provider switching demos."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cloud_storage_api import CloudStorageClient


def run_storage_workflow(
    *,
    client: CloudStorageClient,
    container: str,
    object_name: str,
    data: bytes,
) -> dict[str, Any]:
    """Run upload/list/info/download/delete using only CloudStorageClient API."""
    upload_info = client.upload_obj(container=container, file_obj=BytesIO(data), remote_path=object_name)

    listed = client.list_files(container=container, prefix=object_name)
    info = client.get_file_info(container=container, object_name=object_name)

    with NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        download_info = client.download_file(
            container=container,
            object_name=object_name,
            file_name=str(tmp_path),
        )
        downloaded_bytes = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)

    delete_result = client.delete_file(container=container, object_name=object_name)

    return {
        "upload": upload_info,
        "list": listed,
        "info": info,
        "download": download_info,
        "downloaded_data": downloaded_bytes,
        "delete": delete_result,
    }
