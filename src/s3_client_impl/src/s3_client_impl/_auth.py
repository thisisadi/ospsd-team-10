from __future__ import annotations

import os
from dataclasses import dataclass


class MissingCredentialsError(RuntimeError):
    """Raised when required environment variables are missing."""


@dataclass(frozen=True)
class S3Config:
    bucket: str
    region: str | None


def load_s3_config_from_env() -> S3Config:
    """
    Load S3 configuration from environment variables.

    Required:
      - S3_BUCKET

    Optional:
      - AWS_REGION or AWS_DEFAULT_REGION
    """
    bucket = os.environ.get("S3_BUCKET")
    if not bucket:
        raise MissingCredentialsError("Missing required env var: S3_BUCKET")

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

    return S3Config(bucket=bucket, region=region)