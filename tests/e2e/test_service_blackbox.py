"""Black-box E2E checks by running the service as a subprocess."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from typing import TYPE_CHECKING
from urllib import error, request

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


def _find_free_port() -> int:
    """Return an ephemeral TCP port that is currently free."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, timeout_seconds: float = 15.0) -> None:
    """Wait until /health responds with HTTP 200."""
    deadline = time.time() + timeout_seconds
    health_url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            with request.urlopen(health_url, timeout=1) as response:  # noqa: S310
                if response.status == 200:
                    return
        except (error.URLError, OSError):
            time.sleep(0.2)
    msg = f"Service did not become healthy in {timeout_seconds:.1f}s: {health_url}"
    raise RuntimeError(msg)


@pytest.fixture
def running_service() -> Generator[tuple[str, subprocess.Popen[str]], None, None]:
    """Start vertical_service in a subprocess and yield its base URL."""
    port = _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["HOST"] = "127.0.0.1"
    env["PORT"] = str(port)
    env.setdefault("SESSION_SECRET_KEY", "blackbox-test-secret")

    process = subprocess.Popen(
        [sys.executable, "-m", "vertical_service"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        _wait_for_health(base_url)
        yield base_url, process
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


@pytest.mark.e2e
def test_service_health_blackbox(running_service: tuple[str, subprocess.Popen[str]]) -> None:
    """Service returns 200 on /health when started as a subprocess."""
    base_url, _process = running_service
    with request.urlopen(f"{base_url}/health", timeout=3) as response:  # noqa: S310
        assert response.status == 200
        payload = json.loads(response.read().decode("utf-8"))
    assert payload == {"status": "ok"}


@pytest.mark.e2e
def test_service_openapi_blackbox(running_service: tuple[str, subprocess.Popen[str]]) -> None:
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
def test_service_storage_requires_auth_blackbox(running_service: tuple[str, subprocess.Popen[str]]) -> None:
    """Storage endpoint returns 401 without an authenticated session."""
    base_url, _process = running_service
    with pytest.raises(error.HTTPError) as exc_info:
        request.urlopen(f"{base_url}/storage/files/list?container=test-bucket", timeout=5)  # noqa: S310
    assert exc_info.value.code == 401
