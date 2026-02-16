# ospsd-team-10
Repository for Open Source & Professional Software Development CS-GY 9223

## Team Members
- Aditya Jha (aj4955)
- Pragya Awasthi (pa2755)
- Gurjeet Kaur (gk2845)
- Chloe Lee (hl6181)

---

# Cloud Storage Client — Component-Based Python Implementation

**Assignment**: HW1 — OSPSD CS-GY 9223 (Spring '26)

## Overview

Component-based cloud storage client with abstract interface (`cloud_storage_client_api`) and AWS S3 implementation (`s3_client_impl`). Factory-based dependency injection enables swappable implementations. Strict static analysis (ruff, mypy) and comprehensive test coverage (unit/integration/E2E).

## Architecture

```
components/
├── cloud_storage_client_api/      # Abstract interface (Client ABC, get_client factory)
│   ├── src/cloud_storage_client_api/client.py
│   └── tests/test_interface.py
└── s3_client_impl/                # AWS S3 implementation
    ├── src/s3_client_impl/
    │   ├── client.py (S3CloudStorageClient)
    │   ├── _auth.py (env-based config)
    │   └── __init__.py (auto-registration)
    └── tests/test_aws_impl.py

tests/
├── integration/test_di.py         # DI wiring verification
└── e2e/test_real_s3.py            # Real AWS S3 workflow
```

## Setup & Usage

**Prerequisites**: Python 3.11+, uv package manager

```bash
# Install dependencies
uv venv --python 3.11
source .venv/bin/activate
uv sync --all-packages --group dev

# Basic usage
import s3_client_impl  # Auto-registers S3 implementation
from cloud_storage_client_api.client import get_client

client = get_client()
client.upload_object("bucket", "file.txt", b"data")
client.download_object("bucket", "file.txt")
client.delete_object("bucket", "file.txt")
for name in client.list_objects("bucket"):
    print(name)
```

## Environment Variables

Set for local/E2E testing:
```bash
export AWS_S3_BUCKET="test-bucket"
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="xxx"
export AWS_SECRET_ACCESS_KEY="xxx"
```

In CircleCI: Add these as project environment variables.

## Running Tools

```bash
# Lint & format
uv run ruff check .
uv run ruff format .

# Type check (strict)
uv run mypy components tests

# Tests
uv run pytest                              # All tests
uv run pytest components/ -m "not e2e"    # Unit + integration
uv run pytest tests/e2e/ -m "e2e" -v      # E2E only

# Coverage (threshold: 85%)
uv run pytest --cov=components --cov-report=html
```

## Testing Strategy

- **Unit tests** (`components/*/tests/`): Mocked S3, fast & isolated
- **Integration tests** (`tests/integration/`): Verify DI wiring
- **E2E tests** (`tests/e2e/`): Real AWS S3 workflow, skips if credentials missing

## CI/CD

CircleCI pipeline (`.circleci/config.yml`):
1. **build**: Install deps, verify versions
2. **lint**: ruff check + format
3. **typecheck**: mypy strict
4. **test_unit_integration**: Unit + integration tests, coverage report
5. **test_e2e_optional**: E2E tests (if credentials present)

Artifacts: Coverage reports, test results

## Components

**cloud_storage_client_api**:
- `Client` ABC with 4 abstract methods: `upload_object`, `download_object`, `delete_object`, `list_objects`
- `get_client()` factory for DI
- Zero external dependencies

**s3_client_impl**:
- `S3CloudStorageClient` implements `Client`
- Lazy boto3 init, env-based auth
- `__init__.py` auto-registers factory on import
- Deps: `cloud-storage-client-api`, `boto3>=1.34.0`

## Configuration (pyproject.toml)

**Ruff**: `select = ["ALL"]` with justified ignores  
**MyPy**: `strict = true` with AWS SDK overrides  
**Pytest**: Coverage threshold 85%, test markers (unit/integration/e2e)  
**Root workspace**: Both components listed as members

## Quick Commands

| Task | Command |
|------|---------|
| Install | `uv sync --all-packages --group dev` |
| Lint | `uv run ruff check . && ruff format .` |
| Type | `uv run mypy components tests` |
| Test | `uv run pytest` |
| Coverage | `uv run pytest --cov=components --cov-report=html` |

---

**Last Updated**: Feb 2026
