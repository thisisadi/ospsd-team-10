# Design — Cloud Storage Vertical (HW2 + HW3)

Design and architecture for the cloud storage project (OSPSD CS-GY 9223).
HW1 was a library-style **port** (`Client`) with an S3 **adapter**.
HW2 adds a deployable HTTP **service**, an **OpenAPI-generated client**, and a **remote adapter** so callers can keep using the same `Client` API over the network.
HW3 extends the system with an **AI agent**, **cross-vertical chat integration**, **observability**, and **infrastructure as code**.

---

## Architecture overview

The layout uses **ports and adapters** under `src/`:

```
src/
├── ai_client_api/                    # Port: abstract AIClient, send_message / run_chat_with_tools
├── chat_client_api/                  # Port: abstract ChatClient + DI factory
├── chat_client_service_api_client/   # Generated HTTP client for Team 9's chat service
├── http_chat_client_impl/            # Adapter: ChatClient over Team 9's REST API
├── openai_ai_client_impl/            # Adapter: AIClient over OpenAI Chat Completions
├── vertical_api/                     # Port: abstract Client, DI, result types, typed exceptions
├── vertical_impl/                    # Adapter: S3 + OAuth + token store (registers on import)
├── vertical_service/                 # FastAPI: /health, /auth/*, /storage/*, /agent, /metrics
├── vertical_service_api_client/      # Generated OpenAPI HTTP client
└── vertical_adapter/                 # Adapter: Client over HTTP; vertical_adapter.register() for get_client()
```

| Package                          | Role                                                                                                                          |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ai_client_api`                  | Abstract `AIClient` with `send_message` and `run_chat_with_tools`. No provider SDK leakage.                                   |
| `chat_client_api`                | Abstract `ChatClient` with `send_message` and `check_health`. DI factory via `get_client()`.                                  |
| `chat_client_service_api_client` | Generated HTTP client for Team 9's Slack service. Lazy init, sync/async support, immutable config.                            |
| `http_chat_client_impl`          | `HttpChatClient` implements `ChatClient` over Team 9's REST API. Auto-registers on import.                                    |
| `openai_ai_client_impl`          | `OpenAIAIClient` implements `AIClient`. Single-turn and multi-turn tool-calling loop (up to 8 rounds).                        |
| `vertical_api`                   | Abstract `Client`, `get_client()` / `register_client_factory`, `UploadResult` / `DeleteResult`, exceptions. No HTTP or boto3. |
| `vertical_impl`                  | `S3CloudStorageClient`, OAuth helpers, session-backed token store. Registers the S3 implementation when imported.             |
| `vertical_service`               | FastAPI app: OAuth browser flow, storage routes, `/agent` AI route, `/metrics` Prometheus endpoint.                           |
| `vertical_service_api_client`    | Type-safe client generated from the service OpenAPI spec.                                                                     |
| `vertical_adapter`               | Implements `Client` by delegating to the generated client; maps HTTP status codes to port exceptions.                         |

---

## HW3 — AI Integration

### AI client interface (`ai_client_api`)

The interface is defined as an ABC in a dedicated `.py` file with no provider SDK leakage:

```python
class AIClient(ABC):
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str: ...
    def run_chat_with_tools(self, *, system_prompt, user_message, tools, handle_tool, max_tool_rounds) -> str: ...
```

### OpenAI implementation (`openai_ai_client_impl`)

`OpenAIAIClient` implements `AIClient` against the OpenAI Chat Completions API:

- **`send_message`** — single-turn completion with optional context JSON injected into the system prompt
- **`run_chat_with_tools`** — multi-turn loop that executes tool calls and feeds results back to the model until it responds with text (up to 8 rounds by default)
- Reads `OPENAI_API_KEY` and `OPENAI_MODEL` from environment variables — never hardcoded

### Tool calling wired to domain actions (`agent.py`)

The `/agent` route uses `run_chat_with_tools` with five typed storage tools:

| Tool                       | Domain action                                                  |
| -------------------------- | -------------------------------------------------------------- |
| `create_storage_container` | Creates a new S3 bucket or storage container                   |
| `upload_text_as_file`      | Uploads text content as a file to storage                      |
| `list_storage_files`       | Lists object keys in the container with optional prefix filter |
| `get_storage_file_info`    | Returns metadata (`ObjectInfo`) for a specific object          |
| `summarize_storage_file`   | Downloads a file and returns an AI-generated summary           |

The agent also supports a direct `/summarize <key>` command that bypasses the tool loop for single-step summarization.

Tool results are JSON-serialized and fed back to the model as `tool` role messages. Errors from the storage layer (`StorageBackendError`) are caught and returned as structured JSON so the model can reason about failures.

### Prompt routing

```python
def _route_prompt(message):
    if message.startswith("/summarize "):
        return "summarize_direct", key
    return "chat", None
```

Direct commands skip the tool loop entirely for efficiency. General chat messages go through the full tool-calling loop with a system prompt that instructs the model to prefer tools over guessing.

### Provider swapping

Because the agent depends on the `AIClient` ABC (not `OpenAIAIClient` directly), swapping to Claude or Gemini requires only a new `[provider]_ai_client_impl` that implements the same interface. The `/agent` route, tool definitions, and tool handler do not change.

---

## HW3 — Cross-Vertical Integration

### Shared vertical contract

Team 10 depends on Team 9's chat service via the shared `chat_client_api` ABC:

```python
class ChatClient(ABC):
    def send_message(self, channel: str, text: str) -> str: ...
    def check_health(self) -> bool: ...
```

This interface abstracts Slack (Team 9), Discord (Team 8), and Telegram (Team 4). Swapping providers requires only a different `[platform]_chat_client_impl` — the agent layer never depends on Team 9's API directly.

### Implementation (`http_chat_client_impl`)

`HttpChatClient` implements `ChatClient` over Team 9's REST API:

- Reads `CHAT_SERVICE_BASE_URL` and `CHAT_SESSION_ID` from environment variables
- `send_message` wraps text in a `SendMessageRequest` and POSTs to Team 9's `/messages` endpoint
- `check_health` GETs Team 9's `/health` endpoint — returns `False` if the service is unreachable
- Handles auth errors (401), validation errors (422), and network failures gracefully
- Auto-registers itself as the active chat client on import via `_register_default()`

### Agent integration

The `summarize_and_send` function in `agent.py` accepts an optional `send: Callable[[str], None]` parameter. When provided, it passes the AI-generated summary to the chat client after summarization, enabling the pattern:

```
User → /agent → summarize file → OpenAI → summary → Team 9 Slack channel
```

The agent code depends only on `Callable[[str], None]` — not on `HttpChatClient` or any Slack-specific type.

---

## HW3 — Shared Vertical API (Cloud Storage)

### Interface (`cloud-storage-api` v1.0.0)

All cloud storage teams (Team 2: AWS S3, Team 6: GCP, Team 10: S3) implement the shared `CloudStorageClient` ABC:

```python
def upload_file(container: str, local_path: str, remote_path: str) -> ObjectInfo: ...
def download_file(container: str, object_name: str, file_name: str) -> None: ...
def list_files(container: str, prefix: str = '') -> list[ObjectInfo]: ...
def delete_file(container: str, object_name: str) -> None: ...
def get_file_info(container: str, object_name: str) -> ObjectInfo: ...
```

`ObjectInfo` is a provider-agnostic domain type with fields: `object_name`, `size_bytes`, `data_type`, `version_id`, `integrity`, `encryption`, `storage_tier`, `updated_at`, `metadata`.

### Provider switching

The service selects the storage provider via `STORAGE_PROVIDER`:

| Value          | Implementation                                 |
| -------------- | ---------------------------------------------- |
| `s3` (default) | `S3CloudStorageClient` (Team 10's AWS S3 impl) |
| `gcp`          | `GCPCloudStorageClient` (Google Cloud Storage) |
| `mock`         | In-memory mock for local demo and testing      |

Application and agent code depend only on `CloudStorageClient` — never on provider-specific classes. The same upload/list/info/download/delete workflow runs unchanged across all providers.

---

## HW3 — Observability

### Custom Prometheus metrics (`/metrics`)

A middleware in `app.py` instruments every HTTP request:

| Metric                                     | Type      | Labels               |
| ------------------------------------------ | --------- | -------------------- |
| `vertical_service_requests_total`          | Counter   | `endpoint`, `method` |
| `vertical_service_success_total`           | Counter   | `endpoint`, `method` |
| `vertical_service_failure_total`           | Counter   | `endpoint`, `method` |
| `vertical_service_request_latency_seconds` | Histogram | `endpoint`, `method` |

Success is defined as HTTP status < 400. Failure covers both domain errors (4xx) and infrastructure errors (5xx), satisfying the rubric requirement to distinguish them via labels.

The `/metrics` endpoint exposes all data in Prometheus format, scraped from the live deployed service — not local stdout.

### CloudWatch dashboard

AWS App Runner automatically ships metrics to CloudWatch. The dashboard (`ospsd-team-10`) visualizes:

- **Request latency** — `RequestLatency` line chart
- **Success rate** — `2xxStatusResponses` line chart
- **Failure rate** — `4xxStatusResponses` + `5xxStatusResponses` on the same chart

Both layers (Prometheus + CloudWatch) provide telemetry from the deployed service at:
**`https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics`**

---

## HW3 — IaC & Deployment

### Infrastructure as Code (Terraform)

This repository includes bootstrap Terraform under `infra/terraform/` for shared observability primitives and local environment setup. The full production AWS App Runner stack lives in a dedicated repo ([ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra)). Secrets are supplied through CircleCI/platform/AWS environment mechanisms, not source control.

Infrastructure lives in a dedicated repo ([ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra)) and provisions:

| Resource                                   | Purpose                                                           |
| ------------------------------------------ | ----------------------------------------------------------------- |
| `aws_apprunner_service`                    | Runs the containerized FastAPI app                                |
| `aws_iam_role` (`apprunner-ecr-role`)      | Allows App Runner to pull images from ECR                         |
| `aws_iam_role` (`apprunner-instance-role`) | Allows the app to access S3 without hardcoded credentials         |
| S3 backend (`ospsd-terraform-state`)       | Stores Terraform state for shared access across CI and local runs |

Running `terraform apply` from a clean state produces the full deployed environment. Secrets (API keys, OAuth credentials) are loaded from environment variables — never baked into source control or container images.

### CI/CD pipelines

Two separate CircleCI pipelines:

**App pipeline** (`ospsd-team-10`):

1. Install deps, lint (ruff), type check (mypy)
2. Unit + integration tests, coverage report
3. E2E tests (if AWS credentials present)
4. Build Docker image, tag with `latest` + commit SHA, push to ECR
5. App Runner auto-deploys on new `latest` tag

**Infra pipeline** (`ospsd-team-10-infra`):

1. `terraform init` + `terraform plan`
2. Manual approval gate
3. `terraform apply`

### Deployment

| Environment      | URL                                                   |
| ---------------- | ----------------------------------------------------- |
| HW2 (Render)     | https://team10-cloud-service.onrender.com             |
| HW3 (App Runner) | https://i7bgt2fkwq.us-east-1.awsapprunner.com         |
| API Docs         | https://i7bgt2fkwq.us-east-1.awsapprunner.com/docs    |
| Metrics          | https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics |

---

## HW2 — Architecture overview (unchanged)

### How the pieces interact (remote path)

```
User code
    │
    │  Client API (same as local HW1-style usage)
    ▼
CloudStorageServiceAdapter
    │
    │  generated client (HTTP)
    ▼
vertical_service (FastAPI)
    │
    │  get_client() → S3 impl only
    ▼
S3CloudStorageClient  →  AWS S3
```

### Request flow (example: `list_objects`)

1. User code calls `client.list_objects("my-bucket")`.
2. `CloudStorageServiceAdapter.list_objects` delegates to the generated client.
3. HTTP `GET /storage/my-bucket/objects` with session cookie.
4. `vertical_service` validates session, calls `get_client().list_objects("my-bucket")` → `S3CloudStorageClient`.
5. boto3 `list_objects_v2` runs against S3.
6. Response unwinds: JSON list → parsed list → iterator → caller.

### HTTP API

| Method   | Path                                             | Description                                         |
| -------- | ------------------------------------------------ | --------------------------------------------------- |
| `GET`    | `/health`                                        | Liveness check                                      |
| `GET`    | `/auth/login`                                    | Starts OAuth; redirects to provider                 |
| `GET`    | `/auth/callback`                                 | Handles provider redirect; stores tokens in session |
| `GET`    | `/storage/{container_name}/objects`              | Lists object keys                                   |
| `POST`   | `/storage/{container_name}/objects/{object_key}` | Upload raw body as object                           |
| `GET`    | `/storage/{container_name}/objects/{object_key}` | Download bytes                                      |
| `DELETE` | `/storage/{container_name}/objects/{object_key}` | Delete object                                       |
| `POST`   | `/agent`                                         | AI-powered agent turn                               |
| `GET`    | `/metrics`                                       | Prometheus metrics                                  |

### Error handling (service ↔ port)

| Situation                  | HTTP  | Notes                         |
| -------------------------- | ----- | ----------------------------- |
| FastAPI validation         | `422` | Standard `detail` list        |
| Missing / invalid session  | `401` | `NotAuthenticatedError`       |
| Object not found           | `404` | `ObjectNotFoundError`         |
| Missing AWS / OAuth config | `503` | `MissingCredentialsError`     |
| Upstream failures          | `502` | `StorageOperationFailedError` |
| Other storage failures     | `500` | Generic `StorageError`        |
| OAuth callback errors      | `400` | Provider error / bad request  |

---

## Testing strategy

| Area             | Location                                 | Intent                                                                      |
| ---------------- | ---------------------------------------- | --------------------------------------------------------------------------- |
| AI client        | `src/openai_ai_client_impl/tests/`       | Mocks OpenAI SDK; no network calls                                          |
| Chat client      | `src/http_chat_client_impl/tests/`       | Mocks Team 9's API; no network calls                                        |
| Port / DI        | `src/vertical_api/tests/`                | Interface and registration                                                  |
| S3 impl + OAuth  | `src/vertical_impl/tests/`               | boto3 and HTTP mocked                                                       |
| Service routes   | `src/vertical_service/tests/`            | Auth, storage, agent, error mapping with fakes                              |
| Generated client | `src/vertical_service_api_client/tests/` | Client behavior / parsing                                                   |
| Adapter          | `src/vertical_adapter/tests/`            | HTTP → port errors, delegation                                              |
| Integration      | `tests/integration/`                     | DI wiring, AI tool-call → cross-vertical action pathways                    |
| E2E              | `tests/e2e/`                             | Real S3 when credentials set; black-box assertions on user-visible behavior |

Coverage threshold: **85%** enforced in CI via `pyproject.toml`. Intentionally untestable lines marked `# pragma: no cover`.

---

## Deployment and configuration

| Variable                                  | Purpose                                 |
| ----------------------------------------- | --------------------------------------- |
| `OPENAI_API_KEY`                          | OpenAI credentials                      |
| `OPENAI_MODEL`                            | Model override (default: `gpt-4o-mini`) |
| `AGENT_API_KEY`                           | Shared secret for `/agent` endpoint     |
| `CHAT_SERVICE_BASE_URL`                   | Team 9's service base URL               |
| `CHAT_SESSION_ID`                         | Session credential for Team 9's API     |
| `SESSION_SECRET_KEY`                      | Session cookie signing                  |
| `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` | GitHub OAuth app                        |
| `OAUTH_REDIRECT_URI`                      | Callback URL                            |
| `AWS_S3_BUCKET`, `AWS_REGION`             | S3 bucket and region                    |
| `STORAGE_PROVIDER`                        | Provider selector: `s3`, `gcp`, `mock`  |
