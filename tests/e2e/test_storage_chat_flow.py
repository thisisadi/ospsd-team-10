from __future__ import annotations

import json
from urllib import error, request

import pytest


@pytest.mark.e2e
def test_storage_chat_flow(running_service):
    base_url, _ = running_service

    # 1. Try accessing without auth → should fail
    with pytest.raises(error.HTTPError) as exc:
        request.urlopen(  # noqa: S310
            f"{base_url}/storage/files/list?container=test-bucket",
            timeout=5,
        )

    assert exc.value.code == 401

    # 2. Health check (service is alive)
    with request.urlopen(f"{base_url}/health", timeout=3) as response:  # noqa: S310
        assert response.status == 200

    # 3. OpenAPI includes storage endpoints (integration sanity)
    with request.urlopen(f"{base_url}/openapi.json", timeout=5) as response:  # noqa: S310
        spec = json.loads(response.read().decode("utf-8"))

    assert "/storage/files/upload" in spec["paths"]
    assert "/storage/files/list" in spec["paths"]
    assert "/storage/files/delete" in spec["paths"]
