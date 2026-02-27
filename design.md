# Design Document

This document explains the architecture and design decisions behind the Cloud Storage
Client project, which was built as part of HW1 for OSPSD CS‑GY 9223.

## Goals

* Provide a **clean, testable client** for cloud object storage operations.
* Separate interface from implementation so that providers can be swapped.
* Demonstrate dependency injection, strict typing, and modern tooling.

## Architecture Overview

The repository is organized as a **workspace** with two primary components:

```
components/
├── cloud_storage_client_api/   # Abstract interface and DI helpers
└── s3_client_impl/             # AWS S3 concrete implementation
```

A root `tests/` directory holds integration and end‑to‑end tests.

### Interface Component

* Defines `Client` as an `abc.ABC` with four abstract methods:
  `upload_object`, `download_object`, `delete_object`, `list_objects`.
* Error class `MissingCredentialsError` is provided for configuration failures.
* Dependency injection supported via `register_client_factory`, `register_client`,
  and `get_client()` functions. A mutable list holds the currently registered
  factory to avoid `global` assignment lint warnings.
* The interface package has no external dependencies; it only uses standard
  library typing constructs.

### AWS S3 Implementation

* `S3CloudStorageClient` inherits from `Client` and implements all methods.
* Uses lazy initialization: boto3 client is created only when first needed.
* Configuration (`bucket` and `region`) is loaded from environment variables via
  `load_s3_config_from_env()` in `_auth.py`. Missing bucket raises
  `MissingCredentialsError`.
* A protocol (`_S3Like`) defines the minimal subset of the boto3 client used by
  the implementation, making unit tests simpler to mock.
* The package’s `__init__.py` registers the concrete client factory with the
  interface when imported, ensuring DI wiring happens automatically.

## Dependency Injection Strategy

Consumers import only the interface package and call `get_client()`. The
implementation package registers itself during its import (the side‑effect is
contained and acceptable for this homework). This setup allows other packages to
provide alternative storage backends with zero changes to consumer code.

Unit tests inject mocks directly by creating `S3CloudStorageClient` instances with
fake `_S3Like` objects and `S3Config` instances.

Integration tests simply call `get_client()` after importing the implementation
and assert the returned object’s type and interface compliance.

End‑to‑end tests run against real AWS credentials and exercise the full workflow
(upload → list → download → delete), skipping if environment variables are
absent.

## Tooling and Quality

* ** Ruff **: `select = ["ALL"]` with a handful of documented ignores for
  test files and boto3 naming conventions.
* ** MyPy **: `strict = true` enforced at the root; additional paths added for
  workspace packages. No `# type: ignore` unless strictly necessary.
* ** Pytest **: Custom markers (`unit`, `integration`, `e2e`, `aws_credentials`)
  defined in root `pyproject.toml`. Tests are fast and deterministic.
* ** CircleCI** pipeline orchestrates linting, type checks, unit/integration
  tests, optional e2e runs, and documentation deployment.

## Future Enhancements and Extra Credit Opportunities

* Add additional providers (GCP, Azure) by creating new implementation
  components following the same interface and registration pattern.
* Implement resilience features such as retry/backoff, idempotency, or rate‑limit
  handling inside the implementation.
* Improve error modelling with custom exception classes for typical failure modes.
* Enhance documentation with usage examples, architecture diagrams, and design
  rationales.

This design aims to be simple yet extensible; contributions and refinements are
welcome as the project evolves.