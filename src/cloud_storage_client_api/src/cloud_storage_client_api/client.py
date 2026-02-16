"""Basic cloud storage client interface and factory definition with DI support."""

from abc import ABC, abstractmethod
from collections.abc import Iterator
from typing import Optional

__all__ = ["Client", "get_client", "register_client"]

# Internal variable to hold the registered client implementation
_registered_client: Optional["Client"] = None

class Client(ABC):
    """Defines the common operations that any cloud storage client should support."""

    @abstractmethod
    def upload_object(
        self,
        container_name: str,
        object_name: str,
        data: bytes,
    ) -> None:
        """Upload data as an object inside a container."""
        raise NotImplementedError

    @abstractmethod
    def download_object(
        self,
        container_name: str,
        object_name: str,
    ) -> bytes:
        """Download and return the data of an object from a container."""
        raise NotImplementedError

    @abstractmethod
    def delete_object(
        self,
        container_name: str,
        object_name: str,
    ) -> bool:
        """Delete an object from a container and return True if successful."""
        raise NotImplementedError

    @abstractmethod
    def list_objects(
        self,
        container_name: str,
    ) -> Iterator[str]:
        """Return the names of all objects stored in a container."""
        raise NotImplementedError

def register_client(client: Client) -> None:
    """
    Register a concrete client implementation for Dependency Injection.
    
    When imported, your implementation should call this function to "inject" itself.
    """
    global _registered_client
    _registered_client = client

def get_client(*, interactive: bool = False) -> Client:
    """
    Return the registered cloud storage client instance.

    Raises:
        RuntimeError: if no client has been registered yet.
    """
    if _registered_client is None:
        raise RuntimeError("No cloud client registered. Did you import an implementation?")
    return _registered_client