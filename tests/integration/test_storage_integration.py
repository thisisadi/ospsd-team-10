import http.client
import os
import uuid
from collections.abc import Generator
from urllib.parse import urlparse

import pytest
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient

BASE_URL = os.getenv("SERVICE_BASE_URL", "http://127.0.0.1:8000")
BUCKET = os.getenv("AWS_S3_BUCKET", "test-bucket")
SESSION_TOKEN = os.getenv("INTEGRATION_SESSION_TOKEN")  # optional auth cookie


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
        adapter.delete_object(BUCKET, unique_key)
    except Exception:  # noqa: BLE001
        pass


def test_upload_makes_object_listable(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    data = b"hello integration test"
    adapter.upload_object(BUCKET, unique_key, data)
    objects = list(adapter.list_objects(BUCKET))
    assert unique_key in objects


def test_download_returns_uploaded_content(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    data = b"hello integration test"
    adapter.upload_object(BUCKET, unique_key, data)
    downloaded = adapter.download_object(BUCKET, unique_key)
    assert downloaded == data


def test_delete_removes_object(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    data = b"hello integration test"
    adapter.upload_object(BUCKET, unique_key, data)
    adapter.delete_object(BUCKET, unique_key)
    objects_after = list(adapter.list_objects(BUCKET))
    assert unique_key not in objects_after


def test_full_storage_flow(
    adapter: CloudStorageServiceAdapter,
    unique_key: str,
) -> None:
    """End-to-end: upload -> list -> download -> delete -> verify gone."""
    data = b"hello integration test"
    adapter.upload_object(BUCKET, unique_key, data)
    objects = list(adapter.list_objects(BUCKET))
    assert unique_key in objects
    downloaded = adapter.download_object(BUCKET, unique_key)
    assert downloaded == data
    adapter.delete_object(BUCKET, unique_key)
    objects_after = list(adapter.list_objects(BUCKET))
    assert unique_key not in objects_after
