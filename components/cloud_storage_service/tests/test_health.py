"""Smoke tests for the FastAPI service."""

from __future__ import annotations

import pytest
from cloud_storage_service.app import create_app
from fastapi.testclient import TestClient

pytestmark = pytest.mark.unit


@pytest.fixture
def client() -> TestClient:
    """ASGI test client."""
    return TestClient(create_app())


def test_health_returns_ok(client: TestClient) -> None:
    """GET /health must return 200 and a status payload."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
