"""Basic cloud storage client interface and factory definition."""

from abc import ABC, abstractmethod
from collections.abc import Iterator

__all__ = ["Client", "get_client"]

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

def get_client(*, interactive: bool = False) -> Client:
    """Return a cloud storage client instance."""
    raise NotImplementedError
