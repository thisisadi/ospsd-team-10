# Design — Cloud Storage Vertical (HW2)

Design and architecture for the HW2 extension of the cloud storage project (OSPSD CS-GY 9223). HW1 was a library-style **port** (`Client`) with an S3 **adapter**. HW2 adds a deployable HTTP **service**, an **OpenAPI-generated client**, and a **remote adapter** so callers can keep using the same `Client` API over the network.

---

## Architecture overview

The layout uses **ports and adapters** under `src/`:

```
src/
├── vertical_api/                  # Port: abstract Client, DI, result types, typed exceptions
├── vertical_impl/                 # Adapter: S3 + OAuth + token store (registers on import)
├── vertical_service/              # FastAPI: /health, /auth/*, /storage/* (imports vertical_impl only)
├── vertical_service_api_client/   # Generated OpenAPI HTTP client
└── vertical_adapter/              # Adapter: Client over HTTP; vertical_adapter.register() for get_client()
```

| Package | Role |
|--------|------|
| `vertical_api` | Abstract `Client`, `get_client()` / `register_client_factory`, `UploadResult` / `DeleteResult`, exceptions (`StorageError`, `ObjectNotFoundError`, `NotAuthenticatedError`, `StorageOperationFailedError`, `MissingCredentialsError`). No HTTP or boto3. |
| `vertical_impl` | `S3CloudStorageClient`, OAuth helpers, session-backed token store. Registers the S3 implementation when imported. |
| `vertical_service` | FastAPI app: OAuth browser flow, storage routes that call `get_client()` (always the S3 impl inside the process—never the HTTP adapter, to avoid recursion). |
| `vertical_service_api_client` | Type-safe client generated from the service OpenAPI spec. |
| `vertical_adapter` | Implements `Client` by delegating to the generated client; maps HTTP status codes to **port exceptions** and wire JSON to **port result types**. |

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

---

## Request flow (example: `list_objects`)

1. User code calls `client.list_objects("my-bucket")` (local or remote; same method shape).
2. **`CloudStorageServiceAdapter.list_objects`** delegates to `GeneratedStorageApiClient.list_objects` (generated `list_objects_api.sync_detailed` under the hood).
3. HTTP **`GET`** to the service, e.g.  
   `GET https://<host>/storage/my-bucket/objects`  
   (session cookie present after OAuth.)
4. **`vertical_service`** validates the session, then `get_client().list_objects("my-bucket")` → **`S3CloudStorageClient`**.
5. **boto3** `list_objects_v2` (or equivalent) runs against **S3**.
6. Response unwinds: JSON list from FastAPI → parsed list in generated client → iterator from adapter → caller.

---

## Sample HTTP responses

**`GET /storage/my-bucket/objects`**

```json
["file1.txt", "images/photo.jpg", "data/report.csv"]
```

**`GET /health`**

```json
{ "status": "ok" }
```

**`POST /storage/my-bucket/objects/path/to/file.txt`** (success)

- Status **201 Created**, empty body (upload contract matches `Client.upload_object`).

**`DELETE /storage/my-bucket/objects/file.txt`**

```json
{ "deleted": true }
```

**`422` validation (FastAPI)**

```json
{
  "detail": [
    {
      "loc": ["path", "container_name"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
```

---

## HTTP API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness for load balancers / smoke tests |
| `GET` | `/auth/login` | Starts OAuth; redirects to provider |
| `GET` | `/auth/callback` | Handles provider redirect; exchanges code; stores tokens in session |
| `GET` | `/storage/{container_name}/objects` | Lists object keys |
| `POST` | `/storage/{container_name}/objects/{object_key}` | Upload raw body as object |
| `GET` | `/storage/{container_name}/objects/{object_key}` | Download bytes (`application/octet-stream`) |
| `DELETE` | `/storage/{container_name}/objects/{object_key}` | Deletes object; JSON `{"deleted": bool}` |

### OAuth (browser)

```
Browser                 FastAPI                    OAuth provider
   │                        │                              │
   │  GET /auth/login       │                              │
   │───────────────────────►│                              │
   │  307 → provider        │                              │
   │◄───────────────────────│                              │
   │  GET /authorize?...    │                              │
   │────────────────────────────────────────────────────────►│
   │  302 → /auth/callback?code=…                           │
   │◄────────────────────────────────────────────────────────│
   │  GET /auth/callback    │                              │
   │───────────────────────►│  token exchange              │
   │                        │──────────────────────────────►│
   │                        │◄──────────────────────────────│
   │  redirect / response   │  session stores tokens       │
   │◄───────────────────────│                              │
```

---

## Error handling (service ↔ port)

Storage routes map **port exceptions** to HTTP status (see `vertical_service.routes.storage`). Auth routes use complementary statuses for missing config / OAuth failures.

| Situation | HTTP | Notes |
|-----------|------|--------|
| FastAPI validation | `422` | Standard `detail` list |
| Missing / invalid session (storage) | `401` | `NotAuthenticatedError` |
| Object not found (S3 / port) | `404` | `ObjectNotFoundError` |
| Missing AWS / OAuth **configuration** at runtime | `503` | `MissingCredentialsError` (e.g. `/auth/login`, storage) |
| Upstream / exchange failures | `502` | e.g. token exchange, `StorageOperationFailedError`, failed upload/delete handling |
| Other storage failures | `500` | Generic `StorageError` with safe `detail` |
| OAuth callback (provider error param, bad request) | `400` | Callback validation / provider error |

The adapter maps **HTTP status codes** back to **port-level exceptions** (`NotAuthenticatedError`, `ObjectNotFoundError`, `StorageOperationFailedError`, etc.) so callers using `Client` never depend on raw HTTP types. Delete responses are turned into **`DeleteResult`**; upload success is surfaced as **`UploadResult`** from `CloudStorageServiceAdapter`.

---

## Adapter pattern

### Why it exists

The generated client matches **OpenAPI operations** (sync_detailed, parsed models, status checks), not the **`Client`** ABC. The adapter is the bridge: same `Client` methods externally, HTTP + generated client internally.

### Local vs remote (caller perspective)

**Local (direct S3, HW1-style):**

```python
import vertical_impl  # registers S3 with get_client()
from vertical_api.client import get_client

client = get_client()
client.upload_object("my-bucket", "file.txt", b"hello")
```

**Remote (service + session cookie after OAuth):**

```python
from vertical_adapter.adapter import CloudStorageServiceAdapter, GeneratedStorageApiClient

storage = GeneratedStorageApiClient(
    base_url="https://team10-cloud-service.onrender.com",
    cookies={"session": "<session-from-oauth>"},
)
client = CloudStorageServiceAdapter(storage_api=storage)
```

`vertical_adapter.register()` registers a factory for **`CloudStorageServiceAdapter()`**, which defaults to **`base_url="http://127.0.0.1:8000"`**—fine for local service; for production, prefer an explicit `GeneratedStorageApiClient` + `CloudStorageServiceAdapter(storage_api=...)` (or a custom `register_client_factory`).

### Internals

`CloudStorageServiceAdapter` holds a **`StorageApi`** (`Protocol`): production code uses **`GeneratedStorageApiClient`**; tests inject mocks. Delegation per method; list returns an **iterator** over the list from the wire.

---

## Testing strategy

| Area | Location | Intent |
|------|----------|--------|
| Port / DI | `src/vertical_api/tests/` | Interface and registration |
| S3 impl + OAuth | `src/vertical_impl/tests/` | boto3 and HTTP mocked |
| Service routes | `src/vertical_service/tests/` | Auth, storage, error mapping with fakes |
| Generated client | `src/vertical_service_api_client/tests/` | Client behavior / parsing |
| Adapter | `src/vertical_adapter/tests/` | HTTP → port errors, delegation |
| Integration | `tests/integration/` | Live service: `test_storage_integration.py` (needs running service + `INTEGRATION_SESSION_TOKEN`); `test_di.py` for wiring |
| E2E | `tests/e2e/` | Real S3 (and optional remote) when credentials / env are set |

**Live integration** uses `SERVICE_BASE_URL` (default `http://127.0.0.1:8000`) and **`INTEGRATION_SESSION_TOKEN`** for the session cookie; module skips if `/health` is unreachable or token missing.

**Interface compliance:** `CloudStorageServiceAdapter` subclasses **`Client`** (runtime ABC), **mypy strict** checks types, and integration tests exercise upload / list / download / delete against the service when configured.

---

## Deployment and configuration

Public instance (example): **`https://team10-cloud-service.onrender.com`**. Secrets live in the host (Render / CI), not in git.

**CircleCI** runs ruff, mypy, and tests; optional **Render deploy hook** if `RENDER_DEPLOY_HOOK_URL` is set in CircleCI.

| Variable (representative) | Purpose |
|---------------------------|---------|
| `SESSION_SECRET_KEY` | Session cookie signing |
| `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` | OAuth app |
| `OAUTH_AUTH_URL` / `OAUTH_TOKEN_URL` / `OAUTH_REDIRECT_URI` | Provider endpoints and callback URL |
| `AWS_S3_BUCKET`, `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | S3 access from the service |

---

## OAuth implementation note

Authorization-code helpers (`build_authorization_url`, callback handling) live in **`vertical_impl.oauth`**. The service uses **`vertical_impl`** for those calls and persists tokens via the session-backed store in **`vertical_impl.token_store`**.
