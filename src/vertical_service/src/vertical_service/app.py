"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from vertical_impl.client import S3CloudStorageClient

import http_chat_client_impl  # noqa: F401 — registers Team 9 HTTP chat client for chat_client_api.get_client()
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

    app.state.storage_client = S3CloudStorageClient()

    return app
