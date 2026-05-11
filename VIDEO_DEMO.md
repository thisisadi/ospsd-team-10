# HW3 Video Demo Guide

Use this as the walkthrough script for the OSPSD Spring 2026 HW3 demo.

## 1. Repository and Branch

```bash
git branch --show-current
git status
```

Expected branch: `gurjeet-hw3-new`.

## 2. Local Quality Gate

```bash
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest -v
uv run pytest --cov
```

Explain that pytest includes unit, integration, and black-box e2e tests; live cloud/chat tests skip unless credentials are configured.
Call out that the final run should show 88%+ coverage and zero Ruff/mypy failures.

## 3. App Functionality

Start the service with non-secret local placeholders and mock storage:

```bash
export SESSION_SECRET_KEY="local-demo-session-secret-at-least-32-bytes"
export OPENAI_API_KEY="$OPENAI_API_KEY"
export STORAGE_PROVIDER=mock
uv run python -m vertical_service
```

Then show:

```bash
curl -i http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/openapi.json | python -m json.tool | head
```

## 4. Provider Swapping

Show that the same service selects storage through `STORAGE_PROVIDER`:

- `mock` for local demo and tests
- `s3` for AWS S3
- `gcp` for Google Cloud Storage

The route and agent code stay typed against `cloud-storage-api.CloudStorageClient`.

## 5. AI Tool Calling

Show `src/vertical_service/src/vertical_service/agent.py`:

- `storage_tool_definitions()`
- `_make_tool_handler(...)`
- `run_agent_turn(...)`

Explain the flow: operator prompt -> OpenAI tool call -> storage action -> tool result -> final response.
Mention extra credit: tool schemas come from Pydantic models, and the OpenAI adapter retries transient provider failures.

## 6. Cross-Vertical Integration

Show:

- `chat_client_api` as the shared chat interface
- `http_chat_client_impl` as the Team 9 HTTP adapter
- `tests/integration/test_agent_team9_integration.py` as the live/stubbed integration test

Demo path: AI agent processes a message, uses storage tools, then posts the final response to Team 9 chat.

## 7. Health and Metrics

Local:

```bash
curl -i http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/metrics | grep vertical_service
```

Deployed:

```bash
curl -i https://i7bgt2fkwq.us-east-1.awsapprunner.com/health
curl -s https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics | grep vertical_service
```

Point out labels for `endpoint`, `method`, `status`, and `failure_kind`.
Generate both a 4xx and 5xx locally if time allows, then show `failure_kind="domain"` and `failure_kind="infrastructure"` in `/metrics`.

## 8. CircleCI Walkthrough

Open `.circleci/config.yml` and show:

- `uv sync`
- `uv run ruff check .`
- `uv run ruff format --check .`
- `uv run mypy .`
- `uv run pytest -v`
- `uv run pytest --cov`
- Stored JUnit and coverage artifacts
- Docker publish/deploy jobs gated behind passing checks

## 9. IaC and Deployment

Show:

- Root README links to the shared infra repository.
- `infra/terraform/` contains the local App Runner scaffold.
- Secrets are environment variables or secrets-manager references, not committed files.

## 10. Peer Review Response

Summarize changes made after review:

- Narrow generated-client mypy exclusion.
- Workspace install instead of manual `PYTHONPATH`.
- More explicit telemetry, CI, deployment, and demo documentation.
