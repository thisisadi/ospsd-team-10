from __future__ import annotations

import pytest
from s3_client_impl._auth import MissingCredentialsError, load_s3_config_from_env


def test_load_s3_config_from_env_raises_when_bucket_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("S3_BUCKET", raising=False)
    with pytest.raises(MissingCredentialsError):
        load_s3_config_from_env()


def test_load_s3_config_from_env_reads_bucket_and_region(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("S3_BUCKET", "my-bucket")
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    cfg = load_s3_config_from_env()
    assert cfg.bucket == "my-bucket"
    assert cfg.region == "us-east-1"
