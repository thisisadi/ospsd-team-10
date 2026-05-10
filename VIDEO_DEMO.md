# HW3 Video Demo Checklist

Use this outline while recording the Spring 2026 HW3 demo.

## 1. Application functionality

- Show **OAuth login** (`/auth/login`) or explain session-backed storage when demoing remotely.
- Upload/list/delete an object via **`/storage/*`** routes or describe the OpenAPI flow.
- Trigger **`POST /agent`** with a sample channel id (or explain the Team 9 polling loop).

## 2. Provider swapping

- Set `STORAGE_PROVIDER=mock` locally and run the storage demo / agent tools against the in-memory backend.
- Contrast with `STORAGE_PROVIDER=s3` or `gcp` and note env vars (`AWS_*`, `GCP_*`).

## 3. CircleCI pipeline

- Open the latest pipeline on **`hw-3`** (or `main`): install → **ruff** → **mypy** → **pytest + coverage** → Docker publish → optional deploy hook.
- Highlight uploaded **JUnit** + **coverage HTML/XML** artifacts.

## 4. Tests worth mentioning

- **Unit**: component-colocated tests under `src/*/tests/` with mocked OpenAI / chat HTTP clients.
- **Integration**: `tests/integration/test_ai_tool_cross_vertical_integration.py` — fake OpenAI emits `list_storage_files`, mock storage runs, reply posts through `ChatClient`.
- **E2E**: subprocess black-box service (`tests/e2e/conftest.py`) vs optional **`e2e_live_cloud`** AWS/remote tests. The live-cloud tests are manual and gated by AWS/service env vars.

## 5. Telemetry

- Hit **`/metrics`** on App Runner (Prometheus text format).
- Mention **CloudWatch** metrics automatically emitted by AWS App Runner (`4xx`/`5xx` splits align with middleware semantics).

## 6. Health checks

- Curl **`GET /health`** → `{"status":"ok"}`.

## 7. Links (fill in while recording if URLs rotate)

- Deployed API: `https://i7bgt2fkwq.us-east-1.awsapprunner.com`
- Metrics: `https://i7bgt2fkwq.us-east-1.awsapprunner.com/metrics`
- Grafana / CloudWatch: open the dashboard that charts App Runner request latency and status-class counts.
