# Design — Cloud Storage Vertical (HW2 + HW3)

Design and architecture for the cloud storage project (OSPSD CS-GY 9223).
HW1 was a library-style **port** (`Client`) with an S3 **adapter**.
HW2 adds a deployable HTTP **service**, an **OpenAPI-generated client**, and a **remote adapter** so callers can keep using the same `Client` API over the network.
HW3 extends the system with an **AI agent**, **cross-vertical chat integration**, **observability**, and **infrastructure as code**.

---

## Architecture overview

The layout uses **ports and adapters** under `src/`, plus **Git-installed** course dependencies (for example **`chat-client-api`**) declared in the root `pyproject.toml`:

```
src/
├── ai_client_api/                    # Port: AIClient + register_ai_client / get_ai_client
├── chat_client_service_api_client/   # Generated HTTP client for Team 9's chat service
├── http_chat_client_impl/            # Adapter: Shared ChatClient over Team 9 REST API
├── openai_ai_client_impl/            # Adapter: AIClient over OpenAI; registers default factory on import
├── vertical_api/                     # HW1-style port (under src/; not a uv workspace member)
├── vertical_impl/                    # Adapter: S3 + OAuth + token store
├── vertical_service/                 # FastAPI: /health, /auth/*, /storage/*, /agent, /metrics
├── vertical_service_api_client/      # Generated OpenAPI HTTP client for this service
└── vertical_adapter/                 # Adapter: CloudStorageClient over HTTP; vertical_adapter.register()

infra/terraform/                      # Optional scaffold in this repo; canonical Terraform in ospsd-team-10-infra
```

| Package                          | Role                                                                                                                          |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `ai_client_api`                  | Abstract `AIClient` (`send_message`, `run_chat_with_tools`). `register_ai_client` / `get_ai_client` for DI.                   |
| `chat-client-api` (git)          | Shared `ChatClient` port (`Message`, `Channel`, errors). `register_client(factory)` / `get_client()` — not under `src/`.       |
| `chat_client_service_api_client` | Generated HTTP client for Team 9's Slack service. Lazy init, sync/async support, immutable config.                            |
| `http_chat_client_impl`          | `HttpChatClient` implements Shared `ChatClient`. Registers a **factory** on import.                                          |
| `openai_ai_client_impl`          | `OpenAIAIClient` implements `AIClient`. Registers default factory on import for `get_ai_client()`.                              |
| `vertical_api`                   | HW1-style storage port (optional local usage); not a uv workspace member.                                                     |
| `vertical_impl`                  | S3 + OAuth helpers, session-backed token store.                                                                               |
| `vertical_service`               | FastAPI app: OAuth browser flow, storage routes, `/agent`, `/metrics` (Prometheus + `status_class` labels).                     |
| `vertical_service_api_client`    | Type-safe client generated from the service OpenAPI spec.                                                                     |
| `vertical_adapter`               | Implements `CloudStorageClient` by delegating to the generated client; maps HTTP errors to typed exceptions.                  |

---

## HW3 — AI Integration

### AI client interface (`ai_client_api`)

The interface is defined as an ABC in a dedicated `.py` file with no provider SDK leakage:

```python
class AIClient(ABC):
    def send_message(self, prompt: str, context: dict[str, Any] | None = None) -> str: ...
    def run_chat_with_tools(self, *, system_prompt, user_message, tools, handle_tool, max_tool_rounds) -> str: ...
```

Registry: **`register_ai_client(factory)`** / **`get_ai_client()`** — the FastAPI app calls **`get_ai_client()`** on startup after importing **`openai_ai_client_impl`** so a factory is registered.

`OpenAIAIClient` implements `AIClient` against the OpenAI Chat Completions API:

- **`send_message`** — single-turn completion with optional context JSON injected into the system prompt
- **`run_chat_with_tools`** — multi-turn loop that executes tool calls and feeds results back to the model until it responds with text (up to 8 rounds by default)
- Reads `OPENAI_API_KEY` and `OPENAI_MODEL` from environment variables — never hardcoded
- **`openai_ai_client_impl`** registers a default factory with `register_ai_client` on import; **`vertical_service`** obtains the client via **`get_ai_client()`** at startup (no direct `OpenAIAIClient(...)` construction in the app factory).

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

Because the agent depends on the **`AIClient`** ABC (and **`get_ai_client()`** at the app boundary), swapping to another provider requires a new package that implements the same interface and registers with **`register_ai_client`**. The `/agent` route, tool definitions, and tool handler stay unchanged aside from wiring.

---

## HW3 — Cross-Vertical Integration

### Shared chat port (`chat-client-api`, git)

Team 10 consumes the **course Shared-API** package **`chat-client-api`** (installed from Git; revision pinned in the root `pyproject.toml`). It defines the cross-team **`ChatClient`** ABC, **`Message`** / **`Channel`**, and typed errors such as **`ChatError`**, **`MessageNotFoundError`**, **`MessageDeleteError`**, **`ChannelNotFoundError`**.

- **`register_client(factory)`** — register a **callable** that returns a `ChatClient` (not a long-lived singleton instance).
- **`get_client()`** — returns the configured implementation (raises if nothing registered).

The `/agent` route and **`vertical_service.chat_reply.send_agent_response`** depend only on **`get_client()`** and **`Message`**, not on Team 9's OpenAPI types.

### Implementation (`http_chat_client_impl`)

`HttpChatClient` implements Shared **`ChatClient`** over Team 9's REST API (via **`chat_client_service_api_client`**):

- Reads `CHAT_SERVICE_BASE_URL` and `CHAT_SESSION_ID` from environment variables
- **`send_message`** returns a **`Message`** (opaque `message_id`, timezone-aware `timestamp`, `text`, `sender`, `channel`)
- Implements list/get channel and message operations supported by Team 9; **delete** is not exposed by Team 9 and raises **`MessageDeleteError`** with a clear message
- Registers **`register_client(<factory for HttpChatClient>)`** when **`http_chat_client_impl`** is imported (side effect), so **`vertical_service`** only needs to import that package before calling **`get_client()`**

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

| Metric                                     | Type      | Labels                                      |
| ------------------------------------------ | --------- | ------------------------------------------- |
| `vertical_service_requests_total`          | Counter   | `endpoint`, `method`                        |
| `vertical_service_success_total`           | Counter   | `endpoint`, `method`, `status_class`        |
| `vertical_service_failure_total`           | Counter   | `endpoint`, `method`, `status_class`        |
| `vertical_service_request_latency_seconds` | Histogram | `endpoint`, `method`, `status_class`        |

`status_class` is **`ok`** when the response status is strictly below 400, **`domain_error`** for 4xx responses, and **`infra_error`** for 5xx responses or unhandled exceptions in the metrics middleware. That keeps routing labels (`endpoint`, `method`) bounded while still separating client-style failures from server or transport failures in Prometheus.

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

Infrastructure lives in a dedicated repo ([ospsd-team-10-infra](https://github.com/chloeleehn/ospsd-team-10-infra)) and provisions:

| Resource                                   | Purpose                                                           |
| ------------------------------------------ | ----------------------------------------------------------------- |
| `aws_apprunner_service`                    | Runs the containerized FastAPI app                                |
| `aws_iam_role` (`apprunner-ecr-role`)      | Allows App Runner to pull images from ECR                         |
| `aws_iam_role` (`apprunner-instance-role`) | Allows the app to access S3 without hardcoded credentials         |
| S3 backend (`ospsd-terraform-state`)       | Stores Terraform state for shared access across CI and local runs |

Running `terraform apply` from a clean state produces the full deployed environment. Secrets (API keys, OAuth credentials) are loaded from environment variables — never baked into source control or container images.

**Note:** **`infra/terraform/`** in this application repository is a small, **non-authoritative** scaffold (for reviewers and course alignment). Remote state, approvals, and production-shaped modules live in **ospsd-team-10-infra** above.

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
| AI client        | `src/openai_ai_client_impl/tests/`, `src/ai_client_api/tests/` | Mocks or minimal contracts; no network calls to OpenAI |
| Chat HTTP client | `tests/test_http_chat_client_impl_send_message.py` | Mocks Team 9 HTTP transport; no live network |
| Port / DI        | `src/vertical_api/tests/`                | Interface and registration                                                  |
| S3 impl + OAuth  | `src/vertical_impl/tests/`               | boto3 and HTTP mocked                                                       |
| Service routes   | `src/vertical_service/tests/`            | Auth, storage, agent, error mapping with fakes                              |
| Generated client | `src/vertical_service_api_client/tests/` | Client behavior / parsing                                                   |
| Adapter          | `src/vertical_adapter/tests/`            | HTTP → port errors, delegation                                              |
| Integration      | `tests/integration/`                     | DI wiring, AI tool-call → cross-vertical action pathways                    |
| E2E              | `tests/e2e/`                             | Real S3 when credentials set; black-box assertions on user-visible behavior |

Coverage threshold: **`fail_under = 84`** (`[tool.coverage.report]` in `pyproject.toml`). Intentionally untestable lines are marked `# pragma: no cover`.

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
