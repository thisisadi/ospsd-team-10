from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import httpx
from cloud_storage_service_api_client.client import ApiClient, RequestOptions
from cloud_storage_service_api_client.storage import StorageApiClient

if TYPE_CHECKING:
    import pytest


def test_build_url_trims_slashes() -> None:
    api_client = ApiClient(base_url="http://localhost:8000/")
    assert api_client.build_url("/storage/list") == "http://localhost:8000/storage/list"


def test_request_passes_headers_and_options(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_request(**kwargs: object) -> httpx.Response:
        captured.update(kwargs)
        return httpx.Response(status_code=200, request=httpx.Request("GET", "http://localhost:8000/health"))

    monkeypatch.setattr(httpx, "request", fake_request)
    api_client = ApiClient(base_url="http://localhost:8000", headers={"Authorization": "Bearer abc"})
    api_client.request(
        "GET",
        "/storage/list",
        RequestOptions(params={"container_name": "bucket"}, extra_headers={"X-Test": "1"}),
    )

    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Authorization"] == "Bearer abc"
    assert headers["X-Test"] == "1"
    assert captured["params"] == {"container_name": "bucket"}


def test_storage_client_list_parses_dict_payload() -> None:
    api_client = Mock()
    api_client.request.return_value = Mock(json=Mock(return_value={"objects": ["a", "b", 3]}))
    storage_client = StorageApiClient(api_client=api_client)

    result = storage_client.list_objects("bucket")

    assert result == ["a", "b"]


def test_storage_client_list_parses_list_payload() -> None:
    api_client = Mock()
    api_client.request.return_value = Mock(json=Mock(return_value=["x", "y", 1]))
    storage_client = StorageApiClient(api_client=api_client)

    result = storage_client.list_objects("bucket")

    assert result == ["x", "y"]


def test_storage_client_download_returns_bytes() -> None:
    api_client = Mock()
    api_client.request.return_value = Mock(content=b"hello")
    storage_client = StorageApiClient(api_client=api_client)

    result = storage_client.download_object("bucket", "file.txt")

    assert result == b"hello"
