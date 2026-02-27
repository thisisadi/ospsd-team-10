from __future__ import annotations

import os
from dataclasses import dataclass

from cloud_storage_client_api.client import MissingCredentialsError

_MISSING_S3_BUCKET_MSG = "Missing required env var: AWS_S3_BUCKET"


@dataclass(frozen=True)
class S3Config:
    bucket: str
    region: str | None


def load_s3_config_from_env() -> S3Config:
    """Load S3 configuration from environment variables.

    Required:
      - AWS_S3_BUCKET

    Optional:
      - AWS_REGION or AWS_DEFAULT_REGION
    """
    bucket = os.environ.get("AWS_S3_BUCKET")
    if not bucket:
        raise MissingCredentialsError(_MISSING_S3_BUCKET_MSG)

    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")

    return S3Config(bucket=bucket, region=region)
