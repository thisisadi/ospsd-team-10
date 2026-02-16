from __future__ import annotations

from s3_client_impl.client import S3CloudStorageClient


class FakeS3:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def upload_file(self, filename: str, bucket: str, key: str) -> None:
        self.calls.append(("upload_file", (filename, bucket, key), {}))

    def download_file(self, bucket: str, key: str, filename: str) -> None:
        self.calls.append(("download_file", (bucket, key, filename), {}))

    def delete_object(self, *, Bucket: str, Key: str) -> None:
        self.calls.append(("delete_object", (Bucket, Key), {}))

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict[str, object]:
        self.calls.append(("list_objects_v2", (Bucket, Prefix), {}))
        return {"Contents": [{"Key": f"{Prefix}/a.txt", "Size": 123}]}


class FakeConfig:
    bucket = "test-bucket"
    region = "us-east-1"


def test_upload_calls_s3_upload_file() -> None:
    s3 = FakeS3()
    client = S3CloudStorageClient(s3=s3, config=FakeConfig())  # type: ignore[arg-type]
    out = client.upload("local.txt", "remote.txt")
    assert out == "remote.txt"
    assert ("upload_file", ("local.txt", "test-bucket", "remote.txt"), {}) in s3.calls


def test_download_calls_s3_download_file() -> None:
    s3 = FakeS3()
    client = S3CloudStorageClient(s3=s3, config=FakeConfig())  # type: ignore[arg-type]
    client.download("remote.txt", "local.txt")
    assert ("download_file", ("test-bucket", "remote.txt", "local.txt"), {}) in s3.calls


def test_delete_calls_s3_delete_object() -> None:
    s3 = FakeS3()
    client = S3CloudStorageClient(s3=s3, config=FakeConfig())  # type: ignore[arg-type]
    client.delete("remote.txt")
    assert ("delete_object", ("test-bucket", "remote.txt"), {}) in s3.calls


def test_list_returns_filemeta() -> None:
    s3 = FakeS3()
    client = S3CloudStorageClient(s3=s3, config=FakeConfig())  # type: ignore[arg-type]
    out = client.list("prefix")
    assert len(out) == 1
    assert out[0].path == "prefix/a.txt"
    assert out[0].size == 123
