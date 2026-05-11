from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from vertical_service.app import create_app
from vertical_service.deps import require_oauth_session


class DummyStorageClient:
    def list_files(self, container: str, prefix: str = "") -> list[dict[str, Any]]:
        _ = container
        _ = prefix
        return []


def test_metrics_endpoint() -> None:
    """Validate /metrics endpoint exposes required Prometheus metrics."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/metrics")

    assert response.status_code == 200
    assert "vertical_service_requests_total" in response.text
    assert "vertical_service_success_total" in response.text
    assert "vertical_service_failure_total" in response.text
    assert "vertical_service_request_latency_seconds" in response.text


def test_metrics_updated_after_list_request() -> None:
    """Ensure metrics increment after storage list call."""
    app = create_app()

    # bypass auth
    app.dependency_overrides[require_oauth_session] = lambda: "test-session"

    # mock storage
    app.state.storage_client = DummyStorageClient()

    client = TestClient(app)

    response = client.get("/storage/files/list", params={"container": "test"})
    assert response.status_code == 200

    metrics = client.get("/metrics")

    assert 'vertical_service_requests_total{endpoint="/storage/files/list",method="GET",status="200"}' in metrics.text
    assert 'vertical_service_success_total{endpoint="/storage/files/list",method="GET",status="200"}' in metrics.text


def test_metrics_distinguish_domain_and_infrastructure_failures() -> None:
    """Ensure failure metrics separate 4xx domain errors from 5xx infrastructure failures."""
    app = create_app()

    @app.get("/boom")
    def boom() -> None:
        msg = "boom"
        raise RuntimeError(msg)

    client = TestClient(app, raise_server_exceptions=False)

    not_found_response = client.get("/missing-route")
    auth_response = client.get("/storage/files/info", params={"container": "test", "object_name": "missing"})
    boom_response = client.get("/boom")
    metrics = client.get("/metrics")

    assert not_found_response.status_code == 404
    assert auth_response.status_code == 401
    assert boom_response.status_code == 500
    assert (
        'vertical_service_failure_total{endpoint="/missing-route",failure_kind="domain",method="GET",status="404"}'
        in metrics.text
    )
    assert (
        'vertical_service_failure_total{endpoint="/storage/files/info",failure_kind="domain",method="GET",status="401"}'
        in metrics.text
    )
    assert (
        'vertical_service_failure_total{endpoint="/boom",failure_kind="infrastructure",method="GET",status="500"}' in metrics.text
    )

    app.dependency_overrides.clear()
