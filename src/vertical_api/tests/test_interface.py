import inspect

import pytest
from vertical_api.client import Client, get_client

pytestmark = pytest.mark.unit


def test_interface_is_abstract() -> None:
    """Interface must be abstract."""
    assert inspect.isabstract(Client)


def test_interface_cannot_be_instantiated() -> None:
    """Abstract interface should not be instantiable."""
    with pytest.raises(TypeError):
        type("ConcreteClient", (Client,), {})()


def test_required_methods_exist() -> None:
    """Interface must define all required methods."""
    required_methods = {
        "upload_object",
        "download_object",
        "list_objects",
        "delete_object",
    }

    class_methods = {name for name, value in inspect.getmembers(Client) if callable(value)}

    for method in required_methods:
        assert method in class_methods


def test_method_signatures() -> None:
    """Verify method signatures are correct."""
    method = Client.upload_object
    sig = inspect.signature(method)

    # Expect: self, container_name, object_name, data
    assert len(sig.parameters) == 4


def test_get_client_exists() -> None:
    """Dependency injection function must exist."""
    assert callable(get_client)
