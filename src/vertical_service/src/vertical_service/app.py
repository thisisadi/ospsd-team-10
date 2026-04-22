"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.sessions import SessionMiddleware
from vertical_impl.client import S3CloudStorageClient

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

    # 👇 ADD THIS (metrics endpoint)
    @app.get("/metrics")
    def metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return app
