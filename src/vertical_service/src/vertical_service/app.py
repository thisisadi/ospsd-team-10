"""FastAPI application factory."""

# ruff: noqa: I001
from __future__ import annotations

import vertical_impl  # noqa: F401  # Register S3 implementation with vertical_api DI.
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from vertical_service.config import session_secret_key
from vertical_service.routes import auth, health, storage


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="Cloud Storage Service",
        description="HTTP API for cloud storage with OAuth 2.0 authorization code flow.",
    )
    app.add_middleware(SessionMiddleware, secret_key=session_secret_key())
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(storage.router, prefix="/storage", tags=["storage"])
    return app
