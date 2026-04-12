from vertical_service_api_client import Client
from vertical_service_api_client.api.storage import (
    list_files_storage_files_list_get as list_files_api,
)


def test_generated_client_base_url() -> None:
    client = Client(base_url="http://localhost:8000")
    assert client.get_httpx_client().base_url.host == "localhost"


def test_generated_storage_module_exposes_sync() -> None:
    assert callable(list_files_api.sync)
