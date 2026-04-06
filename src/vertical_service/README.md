# Cloud Storage Service (FastAPI)

Deployable HTTP API for the team’s cloud storage client. It:

- Registers **`vertical_impl`** with `vertical_api` so `get_client()` resolves to S3 (never import `vertical_adapter` here, or storage would call the service over HTTP in a loop).
- Exposes **OAuth 2.0 Authorization Code** endpoints (`/auth/login`, `/auth/callback`) using helpers from `vertical_impl.oauth` and session storage from `vertical_impl.token_store`.
- Maps the abstract `Client` API to HTTP under `/storage/...`.
- Provides **`GET /health`** for probes and **`/openapi.json`** via FastAPI.

## Run locally

From the repository root (with env vars set as below):

```bash
uv run python -m vertical_service
```

Defaults: `HOST=127.0.0.1`, `PORT=8000`. Interactive docs: `http://127.0.0.1:8000/docs`, OpenAPI: `http://127.0.0.1:8000/openapi.json`.

For reload during development:

```bash
UVICORN_RELOAD=1 uv run python -m vertical_service
```

## Environment variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `SESSION_SECRET_KEY` | **Yes** | Secret for signing session cookies (OAuth session id). Use a long random value; never commit it. |
| `OAUTH_CLIENT_ID` | **Yes** (for auth) | OAuth client id from the provider. |
| `OAUTH_CLIENT_SECRET` | **Yes** (for auth) | OAuth client secret. |
| `OAUTH_AUTH_URL` | **Yes** (for auth) | Provider authorization endpoint URL. |
| `OAUTH_TOKEN_URL` | **Yes** (for auth) | Provider token endpoint URL. |
| `OAUTH_REDIRECT_URI` | **Yes** (for auth) | Must match a redirect URI registered at the provider (e.g. `http://127.0.0.1:8000/auth/callback` locally, and your deployed `/auth/callback` in production). |
| `OAUTH_SCOPE` | No | Space-separated scopes, if the provider requires them. |
| `OAUTH_SUCCESS_REDIRECT` | No | Where to send the browser after a successful callback (default `/docs`). |
| `AWS_S3_BUCKET` | **Yes** (for storage calls) | Default bucket when using the S3 implementation. |
| `AWS_REGION` or `AWS_DEFAULT_REGION` | No | AWS region for S3. |
| `HOST` / `PORT` | No | Bind address for `python -m vertical_service`. |

Store secrets in your host or cloud provider’s secret manager in production, not in git.

## HTTP API (summary)

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | No |
| GET | `/auth/login` | No (starts OAuth; uses session cookie) |
| GET | `/auth/callback` | No (browser redirect target; uses session cookie) |
| GET | `/storage/{container}/objects` | Yes (OAuth session with stored token) |
| GET | `/storage/{container}/objects/{object_key:path}` | Yes |
| POST | `/storage/{container}/objects/{object_key:path}` | Yes (raw request body = object bytes) |
| DELETE | `/storage/{container}/objects/{object_key:path}` | Yes |

`object_key:path` allows keys with `/` (e.g. `folder/file.txt`).

## OAuth flow (browser)

1. Open `GET /auth/login` — service assigns a session id, stores CSRF `state`, redirects to the provider.
2. User approves; provider redirects to `GET /auth/callback?code=...&state=...`.
3. Service validates `state`, exchanges `code` for tokens, stores them in `token_store` keyed by session id.
4. Browser is redirected to `OAUTH_SUCCESS_REDIRECT` (default `/docs`).

Storage endpoints require that OAuth has completed for the same browser session (cookie).
