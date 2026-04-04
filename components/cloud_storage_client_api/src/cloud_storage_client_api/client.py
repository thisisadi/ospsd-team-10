"""Basic cloud storage client interface and factory definition with DI support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING


class MissingCredentialsError(RuntimeError):
    """Raised when required credentials or config for a cloud storage provider are missing."""


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_NO_CLIENT_MSG = "No cloud client registered. Did you import an implementation?"

# Use a mutable container to avoid `global` assignment lint (PLW0603).
_registered_factory: list[Callable[[], Client] | None] = [None]


class Client(ABC):
    """Defines the common operations that any cloud storage client should support."""

    @abstractmethod
    def upload_object(self, container_name: str, object_name: str, data: bytes) -> None:
        """Upload data as an object inside a container."""
        raise NotImplementedError

    @abstractmethod
    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download and return the data of an object from a container."""
        raise NotImplementedError

    @abstractmethod
    def delete_object(self, container_name: str, object_name: str) -> bool:
        """Delete an object from a container and return True if successful."""
        raise NotImplementedError

    @abstractmethod
    def list_objects(self, container_name: str) -> Iterator[str]:
        """Return the names of all objects stored in a container."""
        raise NotImplementedError


def register_client_factory(factory: Callable[[], Client]) -> None:
    """Register a concrete client factory for Dependency Injection."""
    _registered_factory[0] = factory


def register_client(client: Client) -> None:
    """Register a concrete client instance for Dependency Injection (compat)."""
    register_client_factory(lambda: client)


def get_client() -> Client:
    """Return a cloud storage client instance.

    Raises:
        RuntimeError: If no client has been registered yet.

    """
    factory = _registered_factory[0]
    if factory is None:
        raise RuntimeError(_NO_CLIENT_MSG)
    return factory()
