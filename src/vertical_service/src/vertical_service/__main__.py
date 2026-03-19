"""Run with: uv run python -m vertical_service."""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")  # noqa: S104
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run(
        "vertical_service.app:create_app",
        host=host,
        port=port,
        factory=True,
        reload=os.environ.get("UVICORN_RELOAD", "").lower() in ("1", "true", "yes"),
    )
