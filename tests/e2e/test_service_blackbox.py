"""Black-box E2E checks by running the service as a subprocess."""

from __future__ import annotations

import json
from urllib import error, request

import pytest


@pytest.mark.e2e
def test_service_health_blackbox(running_service) -> None:
    """Service returns 200 on /health when started as a subprocess."""
    base_url, _process = running_service
    with request.urlopen(f"{base_url}/health", timeout=3) as response:  # noqa: S310
        assert response.status == 200
        payload = json.loads(response.read().decode("utf-8"))
    assert payload == {"status": "ok"}


@pytest.mark.e2e
def test_service_openapi_blackbox(running_service) -> None:
    """OpenAPI is reachable and includes core endpoint paths."""
    base_url, _process = running_service
    with request.urlopen(f"{base_url}/openapi.json", timeout=5) as response:  # noqa: S310
        assert response.status == 200
        spec = json.loads(response.read().decode("utf-8"))
    paths = spec["paths"]
    assert "/health" in paths
    assert "/auth/login" in paths
    assert "/auth/callback" in paths
    assert "/storage/files/upload" in paths


@pytest.mark.e2e
def test_service_storage_requires_auth_blackbox(running_service) -> None:
    """Storage endpoint returns 401 without an authenticated session."""
    base_url, _process = running_service
    with pytest.raises(error.HTTPError) as exc_info:
        request.urlopen(f"{base_url}/storage/files/list?container=test-bucket", timeout=5)  # noqa: S310
    assert exc_info.value.code == 401
