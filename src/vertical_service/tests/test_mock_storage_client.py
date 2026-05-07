from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from cloud_storage_api.exceptions import (
    InvalidContainerError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
)
from vertical_service.provider_switching.mock_storage_client import MockCloudStorageClient

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.unit


def test_upload_file_and_get_file_info(tmp_path: Path) -> None:
    client = MockCloudStorageClient()
    src = tmp_path / "source.txt"
    src.write_bytes(b"hello")

    uploaded = client.upload_file("container", str(src), "a/b.txt")
    info = client.get_file_info("container", "a/b.txt")

    assert uploaded.object_name == "a/b.txt"
    assert info.size_bytes == 5


def test_upload_obj_with_headers_metadata() -> None:
    class _FakeUploadFile(BytesIO):
        def __init__(self) -> None:
            super().__init__(b"payload")
            self.content_type = "text/plain"
            self.headers = {"x-meta": "yes"}

    client = MockCloudStorageClient()
    out = client.upload_obj("container", _FakeUploadFile(), "obj.txt")
    assert out.data_type == "text/plain"
    assert out.metadata == {"x-meta": "yes"}


def test_upload_obj_non_bytes_payload_raises() -> None:
    class _BadFile:
        def read(self) -> str:
            return "not-bytes"

    client = MockCloudStorageClient()
    with pytest.raises(LocalFileAccessError):
        client.upload_obj("container", _BadFile(), "obj.txt")  # type: ignore[arg-type]


def test_download_missing_object_raises(tmp_path: Path) -> None:
    client = MockCloudStorageClient()
    with pytest.raises(ObjectNotFoundError):
        client.download_file("container", "missing.txt", str(tmp_path / "out.txt"))


def test_delete_missing_object_raises() -> None:
    client = MockCloudStorageClient()
    with pytest.raises(ObjectNotFoundError):
        client.delete_file("container", "missing.txt")


def test_list_prefix_filters_results() -> None:
    client = MockCloudStorageClient()
    client.upload_obj("container", BytesIO(b"a"), "docs/a.txt")
    client.upload_obj("container", BytesIO(b"b"), "images/b.png")
    listed = client.list_files("container", "docs/")
    assert [item.object_name for item in listed] == ["docs/a.txt"]


@pytest.mark.parametrize(
    ("method_name", "args", "expected"),
    [
        ("list_files", ("", ""), InvalidContainerError),
        ("upload_obj", ("", BytesIO(b"x"), "obj.txt"), InvalidContainerError),
        ("get_file_info", ("container", ""), InvalidObjectNameError),
    ],
)
def test_validation_errors(
    method_name: str,
    args: tuple[object, ...],
    expected: type[Exception],
) -> None:
    client = MockCloudStorageClient()
    method = getattr(client, method_name)
    with pytest.raises(expected):
        method(*args)
