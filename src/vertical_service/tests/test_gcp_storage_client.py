# ruff: noqa: SLF001
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pytest
from cloud_storage_api.exceptions import (
    AuthenticationError,
    ContainerNotFoundError,
    InvalidContainerError,
    InvalidFileObjectError,
    InvalidObjectNameError,
    LocalFileAccessError,
    ObjectNotFoundError,
    StorageBackendError,
)
from vertical_service.provider_switching.gcp_storage_client import GCPCloudStorageClient

pytestmark = pytest.mark.unit


class _FakeBlob:
    def __init__(
        self,
        name: str,
        *,
        payload: bytes = b"",
        raise_on_reload: Exception | None = None,
        raise_on_delete: Exception | None = None,
    ) -> None:
        self.name = name
        self._payload = payload
        self._raise_on_reload = raise_on_reload
        self._raise_on_delete = raise_on_delete
        self.uploaded_filename: str | None = None
        self.uploaded_file_payload: bytes | None = None
        self.content_type = "text/plain"
        self.etag = "etag-1"
        self.md5_hash = "md5-1"
        self.kms_key_name: str | None = None
        self.storage_class = "STANDARD"
        self.size = len(payload)
        self.generation = 1
        self.updated = datetime(2026, 5, 7, tzinfo=UTC)
        self.metadata: dict[str, str] = {"source": "test"}

    def upload_from_filename(self, file_name: str) -> None:
        self.uploaded_filename = file_name
        self._payload = Path(file_name).read_bytes()
        self.size = len(self._payload)

    def upload_from_file(self, file_obj: BinaryIO, *, rewind: bool) -> None:
        if rewind and hasattr(file_obj, "seek"):
            file_obj.seek(0)
        payload = file_obj.read()
        self.uploaded_file_payload = payload
        self._payload = payload
        self.size = len(payload)

    def reload(self) -> None:
        if self._raise_on_reload:
            raise self._raise_on_reload

    def download_to_filename(self, file_name: str) -> None:
        Path(file_name).write_bytes(self._payload)

    def delete(self) -> None:
        if self._raise_on_delete:
            raise self._raise_on_delete


class _FakeBucket:
    def __init__(
        self,
        *,
        exists_result: bool = True,
        exists_error: Exception | None = None,
        list_blobs_error: Exception | None = None,
    ) -> None:
        self.exists_result = exists_result
        self.exists_error = exists_error
        self.list_blobs_error = list_blobs_error
        self.blobs: dict[str, _FakeBlob] = {}

    def exists(self) -> bool:
        if self.exists_error:
            raise self.exists_error
        return self.exists_result

    def blob(self, object_name: str) -> _FakeBlob:
        return self.blobs.setdefault(object_name, _FakeBlob(object_name))

    def list_blobs(self, *, prefix: str) -> list[_FakeBlob]:
        if self.list_blobs_error:
            raise self.list_blobs_error
        return [blob for name, blob in self.blobs.items() if name.startswith(prefix)]


class _FakeClient:
    def __init__(self, bucket: _FakeBucket) -> None:
        self._bucket = bucket
        self.requested_container: str | None = None

    def bucket(self, container: str) -> _FakeBucket:
        self.requested_container = container
        return self._bucket


def _make_subject(bucket: _FakeBucket) -> GCPCloudStorageClient:
    return GCPCloudStorageClient(client=_FakeClient(bucket), project_id="demo-project")


def test_upload_file_success(tmp_path: Path) -> None:
    bucket = _FakeBucket()
    subject = _make_subject(bucket)
    local_path = tmp_path / "local.txt"
    local_path.write_bytes(b"hello gcp")

    info = subject.upload_file("demo", str(local_path), "remote.txt")

    assert info.object_name == "remote.txt"
    assert info.size_bytes == len(b"hello gcp")
    assert bucket.blob("remote.txt").uploaded_filename == str(local_path)


def test_upload_file_missing_local_path_raises() -> None:
    subject = _make_subject(_FakeBucket())
    with pytest.raises(LocalFileAccessError):
        subject.upload_file("demo", "/missing/file.txt", "remote.txt")


def test_upload_obj_success() -> None:
    bucket = _FakeBucket()
    subject = _make_subject(bucket)

    info = subject.upload_obj("demo", BytesIO(b"obj payload"), "obj.txt")

    assert info.object_name == "obj.txt"
    assert info.size_bytes == len(b"obj payload")
    assert bucket.blob("obj.txt").uploaded_file_payload == b"obj payload"


def test_upload_obj_invalid_file_obj_raises() -> None:
    subject = _make_subject(_FakeBucket())
    with pytest.raises(InvalidFileObjectError):
        subject.upload_obj("demo", None, "obj.txt")  # type: ignore[arg-type]


def test_list_files_returns_sorted_infos() -> None:
    bucket = _FakeBucket()
    bucket.blobs["z-file.txt"] = _FakeBlob("z-file.txt", payload=b"z")
    bucket.blobs["a-file.txt"] = _FakeBlob("a-file.txt", payload=b"a")
    subject = _make_subject(bucket)

    infos = subject.list_files("demo", prefix="")

    assert [item.object_name for item in infos] == ["a-file.txt", "z-file.txt"]


def test_get_file_info_success() -> None:
    bucket = _FakeBucket()
    bucket.blobs["item.txt"] = _FakeBlob("item.txt", payload=b"123")
    subject = _make_subject(bucket)

    info = subject.get_file_info("demo", "item.txt")

    assert info.object_name == "item.txt"
    assert info.size_bytes == 3


def test_download_file_success(tmp_path: Path) -> None:
    bucket = _FakeBucket()
    bucket.blobs["payload.bin"] = _FakeBlob("payload.bin", payload=b"downloaded")
    subject = _make_subject(bucket)
    out_path = tmp_path / "out.bin"

    info = subject.download_file("demo", "payload.bin", str(out_path))

    assert info.object_name == "payload.bin"
    assert out_path.read_bytes() == b"downloaded"


def test_delete_file_success() -> None:
    bucket = _FakeBucket()
    bucket.blobs["to-delete.txt"] = _FakeBlob("to-delete.txt")
    subject = _make_subject(bucket)

    result = subject.delete_file("demo", "to-delete.txt")

    assert result["deleted"] is True


def test_empty_container_raises_invalid_container() -> None:
    subject = _make_subject(_FakeBucket())
    with pytest.raises(InvalidContainerError):
        subject.list_files("", prefix="")


def test_empty_object_name_raises_invalid_object_name() -> None:
    subject = _make_subject(_FakeBucket())
    with pytest.raises(InvalidObjectNameError):
        subject.get_file_info("demo", "")


def test_bucket_forbidden_maps_to_authentication_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ForbiddenError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.Forbidden", _ForbiddenError)
    subject = _make_subject(_FakeBucket(exists_error=_ForbiddenError("forbidden")))
    with pytest.raises(AuthenticationError):
        subject.list_files("demo", prefix="")


def test_bucket_missing_maps_to_container_not_found() -> None:
    subject = _make_subject(_FakeBucket(exists_result=False))
    with pytest.raises(ContainerNotFoundError):
        subject.list_files("demo", prefix="")


def test_list_files_google_api_error_maps_to_storage_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _GoogleAPIError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.GoogleAPIError", _GoogleAPIError)
    subject = _make_subject(_FakeBucket(list_blobs_error=_GoogleAPIError("gcp down")))
    with pytest.raises(StorageBackendError):
        subject.list_files("demo", prefix="")


def test_download_reload_not_found_maps_to_object_not_found(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _NotFoundError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.NotFound", _NotFoundError)
    bucket = _FakeBucket()
    bucket.blobs["missing.txt"] = _FakeBlob("missing.txt", raise_on_reload=_NotFoundError("missing"))
    subject = _make_subject(bucket)
    with pytest.raises(ObjectNotFoundError):
        subject.download_file("demo", "missing.txt", str(tmp_path / "unused"))


def test_delete_reload_not_found_maps_to_object_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class _NotFoundError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.NotFound", _NotFoundError)
    bucket = _FakeBucket()
    bucket.blobs["missing-delete.txt"] = _FakeBlob("missing-delete.txt", raise_on_reload=_NotFoundError("missing"))
    subject = _make_subject(bucket)
    with pytest.raises(ObjectNotFoundError):
        subject.delete_file("demo", "missing-delete.txt")


def test_build_client_requires_project_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    subject = GCPCloudStorageClient(client=None, project_id=None)
    with pytest.raises(ValueError, match="Missing required environment variable: GCP_PROJECT_ID"):
        subject._build_client()


def test_build_client_uses_service_account_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-project")
    monkeypatch.setenv("GCP_CREDENTIALS_PATH", "creds.json")
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    recorded: dict[str, object] = {}

    class _FakeCredentialsFactory:
        @staticmethod
        def from_service_account_file(path: str) -> str:
            recorded["credentials_path"] = path
            return "creds-object"

    def _fake_storage_client(*, project: str, credentials: object | None = None) -> str:
        recorded["project"] = project
        recorded["credentials"] = credentials
        return "client-object"

    monkeypatch.setattr(
        "vertical_service.provider_switching.gcp_storage_client.service_account.Credentials",
        _FakeCredentialsFactory,
    )
    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.storage.Client", _fake_storage_client)

    subject = GCPCloudStorageClient(client=None, project_id=None)
    built = subject._build_client()

    assert built == "client-object"
    assert recorded == {
        "credentials_path": "creds.json",
        "project": "demo-project",
        "credentials": "creds-object",
    }


def test_build_client_uses_default_adc_when_credentials_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GCP_PROJECT_ID", "demo-project")
    monkeypatch.delenv("GCP_CREDENTIALS_PATH", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    recorded: dict[str, object] = {}

    def _fake_storage_client(*, project: str, credentials: object | None = None) -> str:
        recorded["project"] = project
        recorded["credentials"] = credentials
        return "adc-client"

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.storage.Client", _fake_storage_client)

    subject = GCPCloudStorageClient(client=None, project_id=None)
    built = subject._build_client()

    assert built == "adc-client"
    assert recorded == {"project": "demo-project", "credentials": None}


def test_ensure_client_builds_once_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    subject = GCPCloudStorageClient(client=None, project_id="demo-project")
    calls: list[str] = []

    def _fake_build() -> _FakeClient:
        calls.append("build")
        return _FakeClient(_FakeBucket())

    monkeypatch.setattr(subject, "_build_client", _fake_build)

    first = subject._ensure_client()
    second = subject._ensure_client()

    assert first is second
    assert calls == ["build"]


def test_get_bucket_maps_not_found_to_container_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class _NotFoundError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.NotFound", _NotFoundError)
    subject = _make_subject(_FakeBucket(exists_error=_NotFoundError("no bucket")))
    with pytest.raises(ContainerNotFoundError):
        subject.list_files("demo", prefix="")


def test_get_bucket_maps_google_api_error_to_storage_backend_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _GoogleAPIError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.GoogleAPIError", _GoogleAPIError)
    subject = _make_subject(_FakeBucket(exists_error=_GoogleAPIError("backend down")))
    with pytest.raises(StorageBackendError):
        subject.list_files("demo", prefix="")


def test_upload_file_maps_forbidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _ForbiddenError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.Forbidden", _ForbiddenError)
    bucket = _FakeBucket()
    bucket.blobs["blocked.txt"] = _FakeBlob("blocked.txt", raise_on_reload=_ForbiddenError("forbidden"))
    subject = _make_subject(bucket)
    local_path = tmp_path / "in.txt"
    local_path.write_bytes(b"x")
    with pytest.raises(AuthenticationError):
        subject.upload_file("demo", str(local_path), "blocked.txt")


def test_upload_file_maps_not_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _NotFoundError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.NotFound", _NotFoundError)
    bucket = _FakeBucket()
    bucket.blobs["missing.txt"] = _FakeBlob("missing.txt", raise_on_reload=_NotFoundError("missing"))
    subject = _make_subject(bucket)
    local_path = tmp_path / "in.txt"
    local_path.write_bytes(b"x")
    with pytest.raises(ObjectNotFoundError):
        subject.upload_file("demo", str(local_path), "missing.txt")


def test_upload_obj_maps_google_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _GoogleAPIError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.GoogleAPIError", _GoogleAPIError)
    bucket = _FakeBucket()
    bucket.blobs["obj.txt"] = _FakeBlob("obj.txt", raise_on_reload=_GoogleAPIError("gcp down"))
    subject = _make_subject(bucket)
    with pytest.raises(StorageBackendError):
        subject.upload_obj("demo", BytesIO(b"payload"), "obj.txt")


def test_download_file_maps_local_write_error(tmp_path: Path) -> None:
    class _BlobWithOSError(_FakeBlob):
        def download_to_filename(self, _file_name: str) -> None:
            msg = "disk full"
            raise OSError(msg)

    bucket = _FakeBucket()
    bucket.blobs["x.bin"] = _BlobWithOSError("x.bin", payload=b"x")
    subject = _make_subject(bucket)
    with pytest.raises(LocalFileAccessError):
        subject.download_file("demo", "x.bin", str(tmp_path / "x.bin"))


def test_download_file_maps_forbidden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _ForbiddenError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.Forbidden", _ForbiddenError)
    bucket = _FakeBucket()
    bucket.blobs["x.bin"] = _FakeBlob("x.bin", raise_on_reload=_ForbiddenError("forbidden"))
    subject = _make_subject(bucket)
    with pytest.raises(AuthenticationError):
        subject.download_file("demo", "x.bin", str(tmp_path / "x.bin"))


def test_download_file_maps_google_api_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    class _GoogleAPIError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.GoogleAPIError", _GoogleAPIError)
    bucket = _FakeBucket()
    bucket.blobs["x.bin"] = _FakeBlob("x.bin", raise_on_reload=_GoogleAPIError("gcp down"))
    subject = _make_subject(bucket)
    with pytest.raises(StorageBackendError):
        subject.download_file("demo", "x.bin", str(tmp_path / "x.bin"))


def test_list_files_maps_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ForbiddenError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.Forbidden", _ForbiddenError)
    subject = _make_subject(_FakeBucket(list_blobs_error=_ForbiddenError("forbidden")))
    with pytest.raises(AuthenticationError):
        subject.list_files("demo", prefix="")


def test_list_files_maps_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    class _NotFoundError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.NotFound", _NotFoundError)
    subject = _make_subject(_FakeBucket(list_blobs_error=_NotFoundError("missing")))
    with pytest.raises(ContainerNotFoundError):
        subject.list_files("demo", prefix="")


def test_delete_file_maps_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ForbiddenError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.Forbidden", _ForbiddenError)
    bucket = _FakeBucket()
    bucket.blobs["x.txt"] = _FakeBlob("x.txt", raise_on_reload=_ForbiddenError("forbidden"))
    subject = _make_subject(bucket)
    with pytest.raises(AuthenticationError):
        subject.delete_file("demo", "x.txt")


def test_delete_file_maps_google_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _GoogleAPIError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.GoogleAPIError", _GoogleAPIError)

    class _BlobDeleteError(_FakeBlob):
        def delete(self) -> None:
            msg = "backend down"
            raise _GoogleAPIError(msg)

    bucket = _FakeBucket()
    bucket.blobs["x.txt"] = _BlobDeleteError("x.txt")
    subject = _make_subject(bucket)
    with pytest.raises(StorageBackendError):
        subject.delete_file("demo", "x.txt")


def test_get_file_info_maps_forbidden(monkeypatch: pytest.MonkeyPatch) -> None:
    class _ForbiddenError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.Forbidden", _ForbiddenError)
    bucket = _FakeBucket()
    bucket.blobs["x.txt"] = _FakeBlob("x.txt", raise_on_reload=_ForbiddenError("forbidden"))
    subject = _make_subject(bucket)
    with pytest.raises(AuthenticationError):
        subject.get_file_info("demo", "x.txt")


def test_get_file_info_maps_google_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    class _GoogleAPIError(Exception):
        pass

    monkeypatch.setattr("vertical_service.provider_switching.gcp_storage_client.GoogleAPIError", _GoogleAPIError)
    bucket = _FakeBucket()
    bucket.blobs["x.txt"] = _FakeBlob("x.txt", raise_on_reload=_GoogleAPIError("gcp down"))
    subject = _make_subject(bucket)
    with pytest.raises(StorageBackendError):
        subject.get_file_info("demo", "x.txt")
