# s3_client_impl

AWS S3 implementation for the Cloud Storage client.

## Configuration

This implementation uses environment variables:

- `S3_BUCKET` (required)
- `AWS_REGION` or `AWS_DEFAULT_REGION` (optional)
- Standard AWS credentials are read by boto3 (e.g., `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`).

## Usage (scaffold)

```python
from s3_client_impl.client import S3CloudStorageClient

client = S3CloudStorageClient()
# client.upload("local.txt", "remote.txt")