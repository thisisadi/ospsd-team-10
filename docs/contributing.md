# Contributing

How to work on this repository: environment, quality gates, and pull requests.

## Prerequisites

- Python **3.11+**
- **[uv](https://github.com/astral-sh/uv)** for installs and running tools

## Local setup

```bash
uv venv --python 3.11
source .venv/bin/activate   # Windows: .venv\Scripts\activate
uv sync --all-packages --group dev
```

## Before you open a PR

Run the same checks CI runs:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

Optional: build the docs site locally.

```bash
uv run mkdocs build
```

## Code layout

Source lives under `src/` (see [Design](DESIGN.md) for architecture). Tests live under `tests/`. Prefer small, focused changes and tests that cover new behavior or fixes.

## Pull requests

- Use a clear title and description (what changed and why).
- Keep secrets and credentials out of the repo; use environment variables or CI secrets.
- If you touch behavior or public APIs, update README or design docs when it helps reviewers.

## Questions

See **`README.md`** at the repository root for usage, environment variables, and testing notes.
