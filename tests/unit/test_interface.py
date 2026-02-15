import inspect

from cloud_storage_client_api.client import CloudStorageClient
from cloud_storage_client_api.client import get_client


def test_interface_is_abstract():
    assert inspect.isabstract(CloudStorageClient)


def test_required_methods_exist():
    required_methods = {
        "upload_file",
        "download_file",
        "list_files",
        "delete_file",
    }

    class_methods = {
        name
        for name, value in inspect.getmembers(CloudStorageClient)
        if callable(value)
    }

    for method in required_methods:
        assert method in class_methods


def test_get_client_exists():
    assert callable(get_client)
