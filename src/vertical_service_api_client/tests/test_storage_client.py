from vertical_service_api_client.api.storage import (
    list_objects_storage_container_name_objects_get as list_objects_api,
)

from vertical_service_api_client import Client


def test_generated_client_base_url() -> None:
    client = Client(base_url="http://localhost:8000")
    assert client.get_httpx_client().base_url.host == "localhost"


def test_generated_storage_module_exposes_sync() -> None:
    assert callable(list_objects_api.sync)
