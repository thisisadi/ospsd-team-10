# Cloud Storage Client Interface

## Overview
This component defines the **abstract interface** for a cloud storage client.  
It specifies the operations that any cloud storage client implementation must support, such as uploading, downloading, listing, and deleting objects.  

The interface is designed to be implementation-agnostic, allowing any concrete client (AWS S3, GCP, Dropbox, etc.) to be injected through **Dependency Injection (DI)**.

---

## Features
- Define **Abstract Base Class (ABC)** with essential cloud storage operations.
- Supports **Dependency Injection**:
  - Register a concrete client instance or factory.
  - Retrieve the registered client using `get_client()`.
- Clean interface without any implementation-specific dependencies.

---

## Methods

### `upload_object(container_name: str, object_name: str, data: bytes) -> None`
Uploads binary data to a specified container under the given object name.  
- **Parameters**:  
  - `container_name`: Name of the container or bucket.  
  - `object_name`: Name of the object/file to store.  
  - `data`: Binary content to upload.  
- **Returns**: `None`  
- **Behavior**: The interface defines the contract; the implementation handles the actual upload logic.

---

### `download_object(container_name: str, object_name: str) -> bytes`
Retrieves the content of a stored object from a container.  
- **Parameters**:  
  - `container_name`: Name of the container or bucket.  
  - `object_name`: Name of the object/file to download.  
- **Returns**: Binary data of the object.  
- **Behavior**: Raises an error if the object does not exist. The concrete implementation handles connection and retrieval logic.

---

### `delete_object(container_name: str, object_name: str) -> bool`
Deletes a specified object from a container.  
- **Parameters**:  
  - `container_name`: Name of the container or bucket.  
  - `object_name`: Name of the object/file to delete.  
- **Returns**: `True` if the deletion was successful, otherwise `False`.  
- **Behavior**: The implementation ensures safe deletion and handles any errors during the process.

---

### `list_objects(container_name: str) -> Iterator[str]`
Lists all object names stored in a container.  
- **Parameters**:  
  - `container_name`: Name of the container or bucket.  
- **Returns**: An iterator of strings, each representing an object name in the container.  
- **Behavior**: Useful for enumerating all files. The implementation manages paging, filtering, or API-specific calls.

---

## Dependency Injection Functions

### `register_client(client: Client) -> None`
Registers a concrete client instance with the interface.  
- **Parameters**:  
  - `client`: An instance of a class implementing the `Client` ABC.  
- **Returns**: `None`  
- **Behavior**: The registered client will be returned whenever `get_client()` is called.

---

### `register_client_factory(factory: Callable[[], Client]) -> None`
Registers a factory function that returns a client instance.  
- **Parameters**:  
  - `factory`: A callable that produces a `Client` instance.  
- **Returns**: `None`  
- **Behavior**: Allows lazy instantiation or dynamic client creation.

---

### `get_client() -> Client`
Retrieves the registered client instance.  
- **Returns**: An instance of `Client`.  
- **Raises**: `RuntimeError` if no client has been registered yet.  
- **Behavior**: Always returns the client previously registered via `register_client()` or `register_client_factory()`.

---

## Testing Guidelines
- **Interface component** itself does not require unit tests for abstract methods.  
- Integration tests should verify **Dependency Injection** works correctly:
  - Import the implementation package → it automatically registers the client.  
  - `get_client()` should return an instance of the concrete implementation.


