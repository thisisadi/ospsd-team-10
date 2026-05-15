"""Integration tests for CloudStorageServiceAdapter against a live service."""

from __future__ import annotations

import http.client
import os
import tempfile
import uuid
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient

if TYPE_CHECKING:
    from collections.abc import Generator

BASE_URL = os.getenv("SERVICE_BASE_URL", "http://127.0.0.1:8000")
BUCKET = os.getenv("AWS_S3_BUCKET", "test-bucket")
SESSION_TOKEN = os.getenv("INTEGRATION_SESSION_TOKEN")


def is_service_running() -> bool:
    parsed = urlparse(BASE_URL)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    connection_cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    connection = connection_cls(parsed.netloc, timeout=2)
    try:
        connection.request("GET", "/health")
        response = connection.getresponse()
        return bool(response.status == 200)
    except Exception:  # noqa: BLE001
        return False
    finally:
        connection.close()


if not is_service_running():
    pytest.skip("Service not running", allow_module_level=True)


@pytest.fixture
def adapter() -> CloudStorageServiceAdapter:
    if SESSION_TOKEN:
        storage_api = GeneratedStorageApiClient(
            base_url=BASE_URL,
            cookies={"session": SESSION_TOKEN},
        )
        return CloudStorageServiceAdapter(storage_api=storage_api)
    pytest.skip(
        "No INTEGRATION_SESSION_TOKEN set — cannot authenticate against live service. "
        "Run the OAuth flow manually and export the session cookie value."
    )


@pytest.fixture
def unique_key() -> str:
    """Generate a unique object key for each test to avoid collisions."""
    return f"integration-test/{uuid.uuid4()}.txt"


@pytest.fixture(autouse=True)
def cleanup(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> Generator[None, None, None]:
    """Ensure test objects are deleted even if the test fails midway."""
    yield
    try:
        adapter.delete_file(BUCKET, unique_key)
    except Exception:  # noqa: BLE001
        pass


def test_upload_makes_object_listable(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    adapter.upload_obj(BUCKET, BytesIO(b"hello integration test"), unique_key)
    objects = adapter.list_files(BUCKET, prefix="integration-test/")
    keys = [o.object_name for o in objects]
    assert unique_key in keys


def test_download_returns_uploaded_content(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    data = b"hello integration test"
    adapter.upload_obj(BUCKET, BytesIO(data), unique_key)
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        adapter.download_file(BUCKET, unique_key, str(tmp_path))
        downloaded = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
    assert downloaded == data


def test_delete_removes_object(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    adapter.upload_obj(BUCKET, BytesIO(b"hello integration test"), unique_key)
    adapter.delete_file(BUCKET, unique_key)
    objects_after = adapter.list_files(BUCKET, prefix="integration-test/")
    keys = [o.object_name for o in objects_after]
    assert unique_key not in keys


def test_full_storage_flow(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    """End-to-end: upload -> list -> download -> delete -> verify gone."""
    data = b"hello integration test"
    adapter.upload_obj(BUCKET, BytesIO(data), unique_key)

    objects = adapter.list_files(BUCKET, prefix="integration-test/")
    keys = [o.object_name for o in objects]
    assert unique_key in keys

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        adapter.download_file(BUCKET, unique_key, str(tmp_path))
        downloaded = tmp_path.read_bytes()
    finally:
        tmp_path.unlink(missing_ok=True)
    assert downloaded == data

    adapter.delete_file(BUCKET, unique_key)
    objects_after = adapter.list_files(BUCKET, prefix="integration-test/")
    keys_after = [o.object_name for o in objects_after]
    assert unique_key not in keys_after
