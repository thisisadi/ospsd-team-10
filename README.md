# ospsd-team-10

Repository for Open Source & Professional Software Development CS-GY 9223

## Team Members

- Aditya Jha (aj4955)
- Pragya Awasthi (pa2755)
- Gurjeet Kaur (gk2845)
- Chloe Lee (hl6181)

**Related Repositories:** [ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra) — Terraform infrastructure and infra CI/CD pipeline for AWS App Runner deployment

---

# Cloud Storage Client — Component-Based Python Implementation

**Assignment**: HW1 and HW2 — OSPSD CS-GY 9223 (Spring '26)

## Overview

Component-based cloud storage system with:

- Abstract interface (`vertical_api`)
- AWS S3 implementation (`vertical_impl`)
- FastAPI-based cloud storage service
- Adapter + auto-generated client for remote interaction

Supports both **local (direct S3)** and **remote (service via HTTP)** usage.

Includes strict static analysis (ruff, mypy) and comprehensive testing (unit, integration, E2E).

## Documentation

- **[docs/DESIGN.md](docs/DESIGN.md)** — design document (architecture, API decisions, HW2 extension)
- **MkDocs site** — run `uv run mkdocs serve`; the **Design** page is `docs/DESIGN.md`
- **Live site (GitHub Pages)** — [https://thisisadi.github.io/ospsd-team-10/](https://thisisadi.github.io/ospsd-team-10/)

## Architecture

```
src/
├── ai_client_api/                    # Abstract base class (AIClient) for AI providers
├── chat_client_api/                  # Abstract base class (ChatClient) + DI factory for chat providers
├── chat_client_service_api_client/   # Generated HTTP client for Team 9's chat service (auth, sync/async)
├── http_chat_client_impl/            # HttpChatClient: implements ChatClient over Team 9's REST API
├── openai_ai_client_impl/            # OpenAIAIClient: implements AIClient with tool-calling loop
├── vertical_api/                     # Abstract interface, DI, port exceptions / result types
├── vertical_impl/                    # AWS S3 + OAuth + token store (registers on import)
├── vertical_service/                 # FastAPI service — storage, auth, agent (/agent), metrics (/metrics)
├── vertical_service_api_client/      # Generated OpenAPI HTTP client
└── vertical_adapter/                 # Client adapter over HTTP; call vertical_adapter.register() for get_client()

tests/
├── integration/
└── e2e/
```

## Setup

**Prerequisites**: Python 3.12+, uv package manager

```bash
# Install dependencies
uv venv --python 3.12
source .venv/bin/activate
uv sync --all-packages --group dev
```

## Docker (service)

Build and run the FastAPI service container:

```bash
docker build -t ospsd-team-10-service .
docker run --rm -p 8000:8000 \
  -e SESSION_SECRET_KEY="replace-me" \
  -e AWS_S3_BUCKET="your-bucket" \
  -e AWS_ACCESS_KEY_ID="xxx" \
  -e AWS_SECRET_ACCESS_KEY="xxx" \
  -e AWS_REGION="us-east-1" \
  ospsd-team-10-service
```

Then visit:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/openapi.json`

## Usage Examples

### Local Usage (Direct S3)

```python
import vertical_impl  # registers S3 with get_client()
from vertical_api.client import get_client

client = get_client()
client.upload_object("your-bucket-name", "file.txt", b"data")
```

### Remote Usage (Deployed Service)

```python
from vertical_adapter import register
from vertical_api.client import get_client

register()  # wires get_client() to the HTTP adapter
client = get_client()
client.list_objects("your-bucket-name")
```

Or construct the adapter explicitly (e.g. with a session cookie after OAuth):

```python
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient

storage = GeneratedStorageApiClient(
    base_url="https://team10-cloud-service.onrender.com",
    cookies={"session": "<session-cookie-from-oauth>"},
)
client = CloudStorageServiceAdapter(storage_api=storage)
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
uv run mypy .

# Tests
uv run pytest                             # All tests
uv run pytest tests src -m "not e2e"       # Unit + integration
uv run pytest tests/e2e/ -m "e2e" -v      # E2E only

# Coverage (threshold: 85%; matches pyproject source layout)
uv run pytest
```

## Testing Strategy

- **Unit tests** (`src/*/tests/`): Mocked dependencies (fast)
- **Integration tests** (`tests/integration/`): DI wiring; optional live service when env vars are set
- **E2E tests** (`tests/e2e/`): Shared flow helper for **S3** (AWS creds) and **remote adapter** (`SERVICE_BASE_URL`, `INTEGRATION_SESSION_TOKEN`, `AWS_S3_BUCKET`)

## CI/CD

CircleCI pipeline (`.circleci/config.yml`):

1. **build**: Install deps, verify versions, build and push Docker image to ECR
2. **lint**: ruff check + format
3. **typecheck**: mypy strict
4. **test_unit_integration**: Unit + integration tests, coverage report
5. **test_e2e_optional**: E2E tests (if AWS credentials present)
6. **deploy_render_hook** (optional): If `RENDER_DEPLOY_HOOK_URL` is set in CircleCI project env, triggers a Render deploy hook after tests

Artifacts: Coverage reports, test results

## Deployment

### HW2 — Render

**Service URL:** [https://team10-cloud-service.onrender.com](https://team10-cloud-service.onrender.com)  
**API Docs:** [https://team10-cloud-service.onrender.com/docs](https://team10-cloud-service.onrender.com/docs)  
**OpenAPI Schema:** [https://team10-cloud-service.onrender.com/openapi.json](https://team10-cloud-service.onrender.com/openapi.json)

### HW3 — AWS App Runner

**Service URL:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/](https://edbym5kujh.us-east-1.awsapprunner.com)  
**API Docs:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs](https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs)  
**Metrics:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics](https://edbym5kujh.us-east-1.awsapprunner.com/metrics)

Infrastructure is managed via Terraform in [ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra).

## Components

**ai_client_api**:

- `AIClient` ABC defining the minimal contract for AI providers
- Single abstract method: `send_message(prompt, context)` returns a text reply
- Zero external dependencies — decouples agent logic from any specific AI provider

**chat_client_api**:

- `ChatClient` ABC with two abstract methods: `send_message(channel, text)` and `check_health()`
- DI factory (`register_client`, `get_client`) decouples agent code from any specific chat implementation
- Allows swapping real and mock clients without changing core agent logic

**chat_client_service_api_client**:

- Generated HTTP client for Team 9's chat service
- `Client` and `AuthenticatedClient` classes with lazy initialization and context manager support
- Supports both sync (`httpx.Client`) and async (`httpx.AsyncClient`) requests
- Immutable configuration via `with_headers` and `with_cookies` helpers

**http_chat_client_impl**:

- `HttpChatClient` implements `ChatClient` over Team 9's REST API
- Reads `CHAT_SERVICE_BASE_URL` and `CHAT_SESSION_ID` from environment variables
- Handles auth errors, validation errors, and network failures gracefully
- Auto-registers itself as the active chat client on import via `_register_default()`

**openai_ai_client_impl**:

- `OpenAIAIClient` implements `AIClient` using OpenAI Chat Completions
- Single-turn `send_message` with optional context injection into system prompt
- Multi-turn `run_chat_with_tools` loop — executes tool calls until the model responds with text (up to 8 rounds)
- Reads `OPENAI_API_KEY` and `OPENAI_MODEL` from environment variables

**vertical_api**:

- `Client` ABC with 4 abstract methods: `upload_object`, `download_object`, `delete_object`, `list_objects`
- `get_client()` factory for DI
- Zero external dependencies

**vertical_impl**:

- `S3CloudStorageClient` implements `Client`
- Lazy boto3 init, env-based auth
- `__init__.py` auto-registers factory on import
- Deps: `vertical-api`, `boto3>=1.34.0`

**vertical_service**:

- FastAPI service exposing storage, auth, agent, and metrics endpoints
- `/agent` — AI-powered route using `OpenAIAIClient` and tool-calling loop
- `/metrics` — Prometheus metrics endpoint
- Includes health check and optional OAuth flow

**vertical_adapter**:

- Wraps the generated HTTP client as a `Client`; call **`register()`** to use with `get_client()`
- Maps HTTP failures to `vertical_api` exceptions; returns `UploadResult` / `DeleteResult` at the port boundary

## Configuration (pyproject.toml)

**Ruff**: `select = ["ALL"]` with justified ignores  
**MyPy**: `strict = true` with AWS SDK overrides  
**Pytest**: Coverage threshold 85%, test markers (unit/integration/e2e)  
**Root workspace**: Both components listed as members

## Quick Commands

| Task     | Command                                         |
| -------- | ----------------------------------------------- |
| Install  | `uv sync --all-packages --group dev`            |
| Lint     | `uv run ruff check . && ruff format .`          |
| Type     | `uv run mypy .`                                 |
| Test     | `uv run pytest`                                 |
| Coverage | `uv run pytest` (threshold in `pyproject.toml`) |

---

**Last Updated**: May 2026
