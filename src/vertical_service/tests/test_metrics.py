from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from vertical_service.app import create_app
from vertical_service.deps import require_oauth_session


class DummyStorageClient:
    def list_files(self, container: str, prefix: str = "") -> list[dict[str, Any]]:
        return []


def test_metrics_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "vertical_service_requests_total" in response.text
    assert "vertical_service_success_total" in response.text
    assert "vertical_service_failure_total" in response.text
    assert "vertical_service_request_latency_seconds" in response.text


def test_metrics_updated_after_list_request() -> None:
    app = create_app()

    # bypass auth
    app.dependency_overrides[require_oauth_session] = lambda: "test-session"

    # mock storage
    app.state.storage_client = DummyStorageClient()

    client = TestClient(app)

    response = client.get("/storage/files/list", params={"container": "test"})
    assert response.status_code == 200

    metrics = client.get("/metrics")

    assert 'vertical_service_requests_total{endpoint="/storage/files/list",method="GET"}' in metrics.text
    assert 'vertical_service_success_total{endpoint="/storage/files/list",method="GET"}' in metrics.text

    app.dependency_overrides.clear()