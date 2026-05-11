# ruff: noqa: SLF001
from __future__ import annotations

from typing import Any

import pytest
from cloud_storage_api.exceptions import StorageBackendError
from fastapi import FastAPI
from fastapi.testclient import TestClient
from vertical_service.deps import require_oauth_session
from vertical_service.routes import storage as storage_routes

from vertical_service import app as app_mod

pytestmark = pytest.mark.unit


def test_setup_startup_raises_without_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app_mod.setup_startup(app)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    fake_storage = object()

    def _fake_create_storage_client() -> object:
        return fake_storage

    monkeypatch.setattr("vertical_service.app.create_storage_client", _fake_create_storage_client)
    startup = app.router.on_startup[0]
    with pytest.raises(RuntimeError, match="Missing OPENAI_API_KEY"):
        startup()


def test_setup_startup_sets_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    app = FastAPI()
    app_mod.setup_startup(app)
    monkeypatch.setenv("OPENAI_API_KEY", "unit-key")
    fake_storage = object()

    def _fake_create_storage_client() -> object:
        return fake_storage

    def _fake_openai_client(api_key: str) -> dict[str, str]:
        return {"api_key": api_key}

    monkeypatch.setattr("vertical_service.app.create_storage_client", _fake_create_storage_client)
    monkeypatch.setattr("vertical_service.app.OpenAIAIClient", _fake_openai_client)
    startup = app.router.on_startup[0]
    startup()
    assert app.state.storage_client is fake_storage
    assert app.state.ai_client == {"api_key": "unit-key"}


def test_metrics_middleware_failure_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-key-at-least-32-bytes-long")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-key")

    def _fake_create_storage_client() -> object:
        return object()

    def _fake_openai_client(api_key: str) -> dict[str, str]:
        return {"api_key": api_key}

    monkeypatch.setattr("vertical_service.app.create_storage_client", _fake_create_storage_client)
    monkeypatch.setattr("vertical_service.app.OpenAIAIClient", _fake_openai_client)
    app = app_mod.create_app()
    app.dependency_overrides[require_oauth_session] = lambda: "session"

    @app.get("/boom")
    def boom() -> dict[str, Any]:
        msg = "boom"
        raise RuntimeError(msg)

    with TestClient(app) as client, pytest.raises(RuntimeError, match="boom"):
        client.get("/boom")

    metrics = TestClient(app).get("/metrics")
    assert 'failure_kind="infrastructure"' in metrics.text
    assert 'status="500"' in metrics.text


def test_to_http_unexpected_exception_maps_to_500() -> None:
    err = storage_routes._to_http(RuntimeError("unexpected"))
    assert err.status_code == 500
    assert err.detail == "Unexpected storage error."


def test_serialize_variants() -> None:
    class _WithModelDump:
        def model_dump(self) -> dict[str, str]:
            return {"kind": "model_dump"}

    class _WithToDict:
        def to_dict(self) -> dict[str, str]:
            return {"kind": "to_dict"}

    class _Fallback:
        def __init__(self) -> None:
            self.visible = "yes"
            self._hidden = "no"

    assert storage_routes._serialize({"x": 1}) == {"x": 1}
    assert storage_routes._serialize(_WithModelDump()) == {"kind": "model_dump"}
    assert storage_routes._serialize(_WithToDict()) == {"kind": "to_dict"}
    assert storage_routes._serialize(_Fallback())["visible"] == "yes"


def test_storage_delete_and_info_exception_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET_KEY", "test-session-secret-key-at-least-32-bytes-long")
    monkeypatch.setenv("OPENAI_API_KEY", "unit-key")

    class _FailingStorage:
        def delete_file(self, container: str, object_name: str) -> dict[str, bool]:
            _ = (container, object_name)
            msg = "delete down"
            raise StorageBackendError(msg)

        def get_file_info(self, container: str, object_name: str) -> dict[str, str]:
            _ = (container, object_name)
            msg = "info down"
            raise StorageBackendError(msg)

        def list_files(self, container: str, prefix: str = "") -> list[dict[str, str]]:
            _ = (container, prefix)
            return []

        def upload_obj(self, container: str, file_obj: object, remote_path: str) -> dict[str, str]:
            _ = (container, file_obj, remote_path)
            return {"ok": "1"}

        def download_file(self, container: str, object_name: str, file_name: str) -> dict[str, str]:
            _ = (container, object_name, file_name)
            return {"ok": "1"}

    failing_storage = _FailingStorage()

    def _fake_create_storage_client() -> _FailingStorage:
        return failing_storage

    def _fake_openai_client(api_key: str) -> dict[str, str]:
        return {"api_key": api_key}

    monkeypatch.setattr("vertical_service.app.create_storage_client", _fake_create_storage_client)
    monkeypatch.setattr("vertical_service.app.OpenAIAIClient", _fake_openai_client)
    app = app_mod.create_app()
    app.dependency_overrides[require_oauth_session] = lambda: "session"
    app.state.storage_client = failing_storage

    with TestClient(app) as client:
        delete_res = client.delete("/storage/files/delete?container=bucket&object_name=a.txt")
        info_res = client.get("/storage/files/info?container=bucket&object_name=a.txt")

    assert delete_res.status_code == 502
    assert info_res.status_code == 502
