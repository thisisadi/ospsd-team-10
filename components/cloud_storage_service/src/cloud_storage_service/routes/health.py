"""Health check for load balancers and CI."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Return 200 OK when the process is running."""
    return {"status": "ok"}
