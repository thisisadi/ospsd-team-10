# vertical_adapter

Adapter package for HW2 that implements `vertical_api.Client` while delegating to the remote service through `vertical_service_api_client`.

Purpose: keep consumer code unchanged whether using local implementation (`vertical_impl`) or remote service (`vertical_adapter`).

## Dependency injection

Call **`register()`** (from `vertical_adapter`) to register `CloudStorageServiceAdapter` with `vertical_api.register_client_factory`, so `get_client()` returns the remote client.

The FastAPI service (`vertical_service`) must **not** import this package: it uses `vertical_impl` only so storage calls go to S3, not back through HTTP.

## Tests

Unit tests live under `src/vertical_adapter/tests/`. Run with:

`uv run pytest src/vertical_adapter/tests`
