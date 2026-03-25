"""FastAPI application factory."""

from __future__ import annotations

import s3_client_impl  # noqa: F401  # Register S3 implementation with cloud_storage_client_api DI.
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from cloud_storage_service.config import session_secret_key
from cloud_storage_service.routes import auth, health, storage


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
