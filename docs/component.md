# Architecture

The project follows a **component-based architecture**, separating the **interface** from the **implementation**.

- **Interface component** (`cloud_storage_client_api`): Defines the abstract base class (`CloudStorageClient`) and the `get_client()` factory for Dependency Injection.
- **Implementation component** (`s3_client_impl`): Implements the interface and registers itself automatically for use.

This separation allows:

- Switching implementations without changing client code.
- Easier testing via mocks.
- Clean, maintainable code with low coupling.
