from __future__ import annotations

from s3_client_impl.client import S3CloudStorageClient


def test_client_constructs_with_injected_sdk_and_config() -> None:
    class FakeS3:
        pass

    class FakeConfig:
        bucket = "test-bucket"
        region = "us-east-1"

    client = S3CloudStorageClient(s3=FakeS3(), config=FakeConfig())  # type: ignore[arg-type]
    assert client is not None