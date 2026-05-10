# ospsd-team-10

Repository for Open Source & Professional Software Development CS-GY 9223

## Team Members

- Aditya Jha (aj4955)
- Pragya Awasthi (pa2755)
- Gurjeet Kaur (gk2845)
- Chloe Lee (hl6181)

**Related Repositories:** [ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra) — Terraform infrastructure and infra CI/CD pipeline for AWS App Runner deployment  
**HW3 branch:** active development and CircleCI defaults target **`hw-3`** (also **`main`**).

---

# Cloud Storage Client — Component-Based Python Implementation

**Assignment**: HW1–HW3 — OSPSD CS-GY 9223 (Spring ’26)

## Overview

Component-based cloud storage system with:

- Abstract interface (`vertical_api`)
- AWS S3 implementation (`vertical_impl`)
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

- **[docs/DESIGN.md](docs/DESIGN.md)** — canonical design document (architecture, AI tools, cross-vertical integration, observability, testing, peer review)
- **[DESIGN.md](DESIGN.md)** — root pointer to `docs/DESIGN.md`
- **[VIDEO_DEMO.md](VIDEO_DEMO.md)** — demo checklist for the HW3 recording (pipeline, tests, `/health`, `/metrics`)
- **MkDocs** — `uv run mkdocs serve`
- **GitHub Pages** — [https://thisisadi.github.io/ospsd-team-10/](https://thisisadi.github.io/ospsd-team-10/)

### HW3 — Architecture snapshot

- **Storage**: `cloud-storage-api` interface + provider switching (`STORAGE_PROVIDER=s3|gcp|mock`) inside `vertical_service`.
- **AI**: `ai_client_api.AIClient` (ABC: `send_message`, `run_chat_with_tools`) with `openai_ai_client_impl.OpenAIAIClient` (env keys only; Tenacity retries on transient OpenAI errors).
- **Cross-vertical chat**: `chat_client_api` + `http_chat_client_impl` (`get_client()` / `register_client_factory()`); `/agent` never imports Team 9 SDK types directly.
- **IaC**: `infra/terraform/` bootstrap (`terraform init && terraform plan`); production modules remain in **ospsd-team-10-infra**.
- **Telemetry**: Prometheus `/metrics` (latency histogram with `status_class`, separate 4xx/5xx counters) + AWS App Runner → CloudWatch dashboards (see DESIGN.md).

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

**Prerequisites**: Python 3.12+, [uv](https://docs.astral.sh/uv/)

```bash
uv venv --python 3.12
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync --group dev       # installs all workspace packages via root dependency pins — no PYTHONPATH needed
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
uv run ruff check .
uv run ruff format --check .

uv run mypy .

uv run pytest -v
uv run pytest --cov    # same threshold + packages as CI (82%+)

# Focused markers
uv run pytest -m "not team9_chat and not e2e_live_cloud"   # default CI set + subprocess E2E
uv run pytest -m "team9_chat" -v                         # live Team 9 (needs CHAT_* env vars)
uv run pytest -m "e2e_live_cloud" -v                     # real AWS / deployed adapter flows
```

## Testing Strategy

- **Unit / component tests**: Under each package’s `src/<pkg>/tests/` with mocks/fakes (OpenAI SDK never hits network in `openai_ai_client_impl/tests`; HTTP chat patched in `http_chat_client_impl/tests`).
- **Integration tests** (`tests/integration/`): DI wiring (`test_fastapi_di_wiring.py`), provider switching demos, **AI tool → mock storage → ChatClient reply** (`test_ai_tool_cross_vertical_integration.py`), optional live Team 9 harness (`test_agent_team9_integration.py`).
- **E2E** (`tests/e2e/`): `running_service` subprocess black-box tests (`e2e`); AWS / deployed-service flows gated behind `e2e_live_cloud`.
- Live-cloud integration tests such as `tests/integration/test_storage_integration.py` are explicitly marked `e2e_live_cloud` so CI stays deterministic and manual execution is required when AWS/service env vars are available.

## CI/CD

CircleCI (runs on **`hw-3`** and **`main`**):

1. **`install_workspace`** — `uv sync --group dev` (no `PYTHONPATH`).
2. **`lint`** — `uv run ruff check .` + `ruff format --check`.
3. **`typecheck`** — `uv run mypy .` (strict).
4. **`test_all`** — `pytest -m "not team9_chat and not e2e_live_cloud"` with coverage XML/HTML artifacts + **`--cov-fail-under=84`** (JUnit uploaded).
5. **`test_team9_chat_optional`** / **`test_e2e_live_cloud_optional`** — run only when the respective secrets/env vars exist.
6. **`docker_build_push`** — requires lint + typecheck + **`test_all`** (AWS CLI + ECR login secrets supplied via CircleCI contexts/project settings — never committed).
7. **`deploy_render_hook`** — runs only after **`docker_build_push`** succeeds (`RENDER_DEPLOY_HOOK_URL` from context).

Bootstrap IaC locally: `cd infra/terraform && terraform init`

## Deployment

### HW2 — Render

**Service URL:** [https://team10-cloud-service.onrender.com](https://team10-cloud-service.onrender.com)  
**API Docs:** [https://team10-cloud-service.onrender.com/docs](https://team10-cloud-service.onrender.com/docs)  
**OpenAPI Schema:** [https://team10-cloud-service.onrender.com/openapi.json](https://team10-cloud-service.onrender.com/openapi.json)

### HW3 — AWS App Runner

**Service URL:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com](https://i7bgt2fkwq.us-east-1.awsapprunner.com)  
**API Docs:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs](https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs)  
**Metrics:** [https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics](https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics)

This repo includes bootstrap Terraform under `infra/terraform/`, while the full production AWS App Runner stack is maintained in the dedicated repo [ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra). Secrets are supplied through CircleCI/platform/AWS environment mechanisms, not source control.

Infrastructure is managed via Terraform in [ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra).

## Components

**ai_client_api**:

- `AIClient` ABC (`send_message`, `run_chat_with_tools`) — framework-free port with zero provider SDK leakage
- Implemented by `openai_ai_client_impl.OpenAIAIClient` (reads `OPENAI_API_KEY` / `OPENAI_MODEL` only from env)

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
- Registers via `_register_default()` **only if** no chat implementation has called `register_client_factory` yet (tests can inject fakes first)

**openai_ai_client_impl**:

- `OpenAIAIClient` implements `AIClient` using OpenAI Chat Completions
- Tenacity retries on rate limits / connection timeouts around `chat.completions.create`
- Typed storage tool **schemas** are authored as Pydantic models in `vertical_service.storage_tool_models` and exported as OpenAI-compatible JSON schemas

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

**Ruff**: `select = ["ALL"]` with justified `per-file-ignores` for ABC-heavy modules/tests  
**MyPy**: `strict = true` (+ Prometheus stubs override)  
**Pytest / Coverage**: Multi-package `--cov`, **`fail_under = 82`**, markers (`e2e`, `e2e_live_cloud`, `team9_chat`, …)  
**Workspace**: All HW3 packages are `[tool.uv.workspace]` members **and** explicit root dependencies so editable installs work with plain `uv sync`.

## Quick Commands

| Task     | Command                                  |
| -------- | ---------------------------------------- |
| Install  | `uv sync --group dev`                    |
| Lint     | `uv run ruff check .`                    |
| Format   | `uv run ruff format --check .`           |
| Type     | `uv run mypy .`                          |
| Test     | `uv run pytest -v`                       |
| Coverage | `uv run pytest --cov`                    |

---

**Last Updated**: May 2026
