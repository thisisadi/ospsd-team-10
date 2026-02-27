# Contributing

Thanks for your interest in contributing to the Cloud Storage Client project!

## Getting Started

1. **Fork** the repository and create a branch off `main` (e.g. `feature/your-change`).
2. Make sure you have a Python 3.11 environment and `uv` installed.
3. Run `uv venv --python 3.11 && source .venv/bin/activate && uv sync --all-packages --group dev`.
4. Run lint, typechecks, and tests locally before opening a PR:
   ```bash
   uv run ruff check .
   uv run mypy components tests
   uv run pytest
   ```

## Coding Guidelines

* Follow the existing component-based structure. New components should live under `components/*`.
* Use **absolute imports** exclusively; avoid `__all__` except when re-exporting in top-level `__init__.py`.
* Interfaces live in the API package and use `abc.ABC`; implementations should not depend on concrete SDKs.
* Add unit tests under the component's `tests/` folder and annotate them with `@pytest.mark.unit`.
* Integration tests go in `tests/integration/`; e2e tests in `tests/e2e/` with appropriate markers.
* Keep commits small and messages imperative. PRs should target `main` from a feature branch.

## Pull Request Process

1. Open a PR against `main` and select the **HW‑1** label if appropriate.
2. Include a summary, affected areas checklist (see `.github/pull_request_template.md`).
3. Ensure CI is green (lint, mypy, tests) and coverage meets threshold.
4. Address review comments promptly.

## Style & Tools

* Ruff is used for linting/formatting (`select = ["ALL"]` in root `pyproject.toml`).
* MyPy is configured with `strict = true`; avoid blanket `# type: ignore`.
* Tests are run with `pytest` and coverage is measured; aim for >85% coverage.

## Documentation

* Add or update docs in `docs/` and ensure `mkdocs build` succeeds.
* Component READMEs should describe API, usage, and design rationale.

Thanks for contributing—your feedback and code help keep the project clean and maintainable!