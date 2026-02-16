import inspect

import pytest
from cloud_storage_client_api.client import CloudStorageClient, get_client


def test_interface_is_abstract():
    """Interface must be abstract."""
    assert inspect.isabstract(CloudStorageClient)


def test_interface_cannot_be_instantiated():
    """Abstract interface should not be instantiable."""
    with pytest.raises(TypeError):
        CloudStorageClient()


def test_required_methods_exist():
    """Interface must define all required methods."""
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


def test_method_signatures():
    """Verify method signatures are correct."""
    method = CloudStorageClient.upload_file
    sig = inspect.signature(method)

    # Expect: self, local_path, remote_path
    assert len(sig.parameters) == 3


def test_get_client_exists():
    """Dependency injection function must exist."""
    assert callable(get_client)
