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

**Assignment**: HW1–HW3 — OSPSD CS-GY 9223 (Spring '26)

## Overview

Component-based cloud storage system with:

- Shared storage port (**`cloud-storage-api`**) consumed by the service and agent tools
- Optional HW1-style **`vertical_api`** tree under `src/` for some local examples (not a uv workspace member)
- AWS S3 implementation (`vertical_impl`) plus GCP and mock providers for demos
- FastAPI-based cloud storage service
- Adapter + auto-generated client for remote interaction

Supports both **local (direct S3)** and **remote (service via HTTP)** usage.

Includes strict static analysis (ruff, mypy) and comprehensive testing (unit, integration, E2E).

## HW3 Provider Switching Demo

The storage provider is selected by configuration through `STORAGE_PROVIDER`:

- `STORAGE_PROVIDER=s3` uses the existing `S3CloudStorageClient` implementation.
- `STORAGE_PROVIDER=gcp` uses `GCPCloudStorageClient` (Google Cloud Storage).
- `STORAGE_PROVIDER=mock` uses an in-memory mock implementation for local demo/testing.
- If `STORAGE_PROVIDER` is unset, the service defaults to `s3` to preserve existing teammate workflows.
- GCP configuration uses `GCP_PROJECT_ID` plus either `GCP_CREDENTIALS_PATH` or `GOOGLE_APPLICATION_CREDENTIALS`.
- For GCP workflows, pass the bucket as the normal `container` argument; optional test helpers can use `GCP_BUCKET_NAME` (or `GCP_BUCKET`).

Application and demo workflow code depend only on the shared `CloudStorageClient` interface (`cloud-storage-api` v1.0.0), not provider-specific logic. The same upload/list/info/download/delete workflow can run against S3, GCP, or mock, demonstrating provider swapping for the HW3 video requirement.

## Documentation

- **[docs/DESIGN.md](docs/DESIGN.md)** — design document (architecture, API decisions, HW2 extension)
- **MkDocs site** — run `uv run mkdocs serve`; the **Design** page is `docs/DESIGN.md`
- **Live site (GitHub Pages)** — [https://thisisadi.github.io/ospsd-team-10/](https://thisisadi.github.io/ospsd-team-10/)

## Architecture

The root **`pyproject.toml`** defines a **uv workspace** for the service and adapters. Some dependencies are **not** under `src/`:

- **`chat-client-api`** — shared chat vertical port (`ChatClient`, `Message`, `Channel`, errors, `register_client` / `get_client`), installed from **Git** ([Shared-API](https://github.com/HarshithKoriRaj/Shared-API)); the exact revision is pinned in **`[tool.uv.sources]`**.
- **`cloud-storage-api`** — shared storage port used by the service and agent tools (git dependency).

```
src/
├── ai_client_api/                    # ABC: AIClient; register_ai_client / get_ai_client
├── chat_client_service_api_client/   # Generated OpenAPI client for Team 9's chat HTTP API
├── http_chat_client_impl/            # HttpChatClient (Shared ChatClient); factory registration on import
├── openai_ai_client_impl/            # OpenAIAIClient; registers default AI factory on import
├── vertical_api/                     # HW1-style port package (under src/; not a uv workspace member)
├── vertical_impl/                    # S3 + OAuth + token store (workspace package)
├── vertical_service/                 # FastAPI: storage, auth, /agent, /metrics
├── vertical_service_api_client/      # Generated client for this service's OpenAPI
└── vertical_adapter/                 # Remote storage: register() then vertical_api-style get_client()

infra/terraform/                      # Small Terraform scaffold for reviewers; production IaC is in ospsd-team-10-infra

tests/
├── integration/
├── test_http_chat_client_impl_send_message.py
└── e2e/
```

## Setup

**Prerequisites**: Python **3.12** (project requires `>=3.12,<3.13`), **uv**

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

**Team 9 + `/agent` integration (CI):** To run the live chat integration test on every pipeline, add project environment variables:

- `CHAT_SERVICE_BASE_URL` — Team 9 chat API base URL (same as production usage).
- `CHAT_SESSION_ID` — Session id sent as `X-Session-ID` (list + post messages).
- `INTEGRATION_AGENT_CHANNEL_ID` — A dedicated channel id for automation (tests post a unique probe message and the agent reply there).

Optional: `AGENT_API_KEY` — if set, the test sends matching `X-API-Key` on `POST /agent` (same as your deployed service).

## Running Tools

```bash
# Lint & format
uv run ruff check .
uv run ruff format .

# Type check (strict)
uv run mypy .

# Tests
uv run pytest                             # All tests
uv run pytest tests src -m "not e2e and not team9_chat"   # Unit + integration (excludes live Team 9)
uv run pytest -m "team9_chat" -v          # Team 9 + stub AI (needs CHAT_* + INTEGRATION_AGENT_CHANNEL_ID)
uv run pytest tests/e2e/ -m "e2e" -v      # E2E only

# Coverage (fail_under=84 in pyproject.toml; see [tool.coverage.report])
uv run pytest
```

## Testing Strategy

- **Unit tests** (`src/*/tests/` and root **`tests/`**): Mocked dependencies (fast); **`tests/test_http_chat_client_impl_send_message.py`** covers **`HttpChatClient`** send path
- **Integration tests** (`tests/integration/`): DI wiring; optional live storage service; **Team 9** (`tests/integration/test_agent_team9_integration.py`) when `CHAT_SERVICE_BASE_URL`, `CHAT_SESSION_ID`, and `INTEGRATION_AGENT_CHANNEL_ID` are set (stub AI, mock storage — no OpenAI)
- **E2E tests** (`tests/e2e/`): Shared flow helper for **S3** (AWS creds) and **remote adapter** (`SERVICE_BASE_URL`, `INTEGRATION_SESSION_TOKEN`, `AWS_S3_BUCKET`)

## CI/CD

CircleCI pipeline (`.circleci/config.yml`):

1. **build**: Install deps, verify versions, build and push Docker image to ECR
2. **lint**: ruff check + format
3. **typecheck**: mypy strict
4. **test_unit_integration**: Unit + integration tests, coverage report (excludes `team9_chat` marks)
5. **test_team9_chat_optional**: Live Team 9 poll + reply + in-process `/agent` with stub AI (if `CHAT_*` and `INTEGRATION_AGENT_CHANNEL_ID` are set)
6. **test_e2e_optional**: E2E tests (if AWS credentials present)
7. **deploy_render_hook** (optional): If `RENDER_DEPLOY_HOOK_URL` is set in CircleCI project env, triggers a Render deploy hook after tests

Artifacts: Coverage reports, test results

## Deployment

### HW2 — Render

**Service URL:** [https://team10-cloud-service.onrender.com](https://team10-cloud-service.onrender.com)  
**API Docs:** [https://team10-cloud-service.onrender.com/docs](https://team10-cloud-service.onrender.com/docs)  
**OpenAPI Schema:** [https://team10-cloud-service.onrender.com/openapi.json](https://team10-cloud-service.onrender.com/openapi.json)

### HW3 — AWS App Runner

**Service URL:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com](https://i7bgt2fkwq.us-east-1.awsapprunner.com)  
**API Docs:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs](https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs)  
**Metrics:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics](https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics)

Infrastructure is managed in **[ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra)** (Terraform, state, infra CI). This repo also contains a small **`infra/terraform/`** scaffold so reviewers can see expected App Runner resources without duplicating the full production stack.

## Components

**ai_client_api** (workspace):

- `AIClient` ABC: `send_message`, `run_chat_with_tools` (tool loop contract)
- `register_ai_client` / `get_ai_client` — decouples the service from a concrete LLM SDK

**chat-client-api** (git / Shared-API):

- `ChatClient` ABC (full cross-team contract: send/list channels/messages, get/delete where supported)
- `Message`, `Channel`, typed errors (`ChatError`, `MessageNotFoundError`, …)
- `register_client(factory: Callable[[], ChatClient])` and `get_client()`

**chat_client_service_api_client** (workspace):

- Generated HTTP client for Team 9's chat service (sync/async, OpenAPI models)

**http_chat_client_impl** (workspace):

- `HttpChatClient` implements Shared `ChatClient` over Team 9's REST API
- Reads `CHAT_SERVICE_BASE_URL` and `CHAT_SESSION_ID`
- Registers a **factory** on import (`register_client(...)`); failures surface as `ChatError` (and subclasses where applicable)

**openai_ai_client_impl** (workspace):

- `OpenAIAIClient` implements `AIClient` (OpenAI SDK)
- Registers the default factory on package import; `vertical_service` uses `get_ai_client()` at startup
- Reads `OPENAI_API_KEY` and optional `OPENAI_MODEL`

**vertical_api** (under `src/`, not a uv workspace member):

- HW1-style storage port and `get_client()` used in some **local** / course examples (see Usage Examples below)

**vertical_impl** (workspace):

- AWS S3 + OAuth + token store; boto3-backed implementation for the service

**vertical_service** (workspace):

- FastAPI app: OAuth, storage routes, **`POST /agent`**, **`GET /metrics`**
- Prometheus middleware labels include **`status_class`** (`ok`, `domain_error`, `infra_error`) on success, failure, and latency series
- Agent replies use **`vertical_service.chat_reply.send_agent_response`** → Shared `get_client().send_message(...)`

**vertical_adapter** (workspace):

- Remote **`CloudStorageClient`** over this service's HTTP API; **`register()`** for adapter wiring

## Configuration (pyproject.toml)

**Ruff**: `select = ["ALL"]` with justified ignores  
**MyPy**: `strict = true` with AWS SDK overrides  
**Pytest**: Coverage **`fail_under = 84`** (`[tool.coverage.report]`), test markers (unit / integration / e2e / `team9_chat`)  
**Root workspace**: Members listed in `[tool.uv.workspace]`; external packages pinned under `[tool.uv.sources]`

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
