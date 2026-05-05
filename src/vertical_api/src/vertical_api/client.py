"""Basic cloud storage client interface and factory definition with DI support."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


class MissingCredentialsError(RuntimeError):
    """Raised when required credentials or config for a cloud storage provider are missing."""


class StorageError(RuntimeError):
    """Base class for storage failures at the port boundary."""


class ObjectNotFoundError(StorageError):
    """Raised when the requested object (or key) does not exist."""


class NotAuthenticatedError(StorageError):
    """Raised when the caller is not authorized for the storage operation."""


class StorageOperationFailedError(StorageError):
    """Raised when a storage operation fails for a generic or provider-specific reason."""


@dataclass(frozen=True)
class UploadResult:
    """Outcome of an upload at the port layer (framework-agnostic)."""

    success: bool
    container_name: str
    object_key: str
    etag: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class DeleteResult:
    """Outcome of a delete at the port layer (framework-agnostic)."""

    success: bool
    object_key: str
    detail: str | None = None


if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

_NO_CLIENT_MSG = "No cloud client registered. Did you import an implementation?"

# Use a mutable container to avoid `global` assignment lint (PLW0603).
_registered_factory: list[Callable[[], Client] | None] = [None]


class Client(ABC):
    """Defines the common operations that any cloud storage client should support."""

    @abstractmethod
    def upload_object(self, container_name: str, object_name: str, data: bytes) -> object | None:
        """Upload data as an object inside a container.

        Implementations should return :class:`UploadResult` or a provider-specific result object,
        or ``None`` if they do not expose structured outcomes.
        """
        raise NotImplementedError

    @abstractmethod
    def download_object(self, container_name: str, object_name: str) -> bytes:
        """Download and return the data of an object from a container."""
        raise NotImplementedError

    @abstractmethod
    def delete_object(self, container_name: str, object_name: str) -> object:
        """Delete an object from a container.

        Implementations should return :class:`DeleteResult` or a provider-specific result object.
        """
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
