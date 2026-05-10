"""FastAPI application factory and configuration."""

import logging
import os
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.sessions import SessionMiddleware

import http_chat_client_impl  # noqa: F401
import openai_ai_client_impl  # noqa: F401
from ai_client_api import get_client as get_ai_client
from vertical_service.config import session_secret_key
from vertical_service.provider_switching.factory import create_storage_client
from vertical_service.routes import agent, auth, health, storage

logger = logging.getLogger(__name__)
HTTP_BAD_REQUEST = 400


# ---- Metrics setup ----
def setup_metrics(app: FastAPI) -> CollectorRegistry:
    """Configure Prometheus metrics and attach middleware to the app."""
    registry = CollectorRegistry()

    request_count = Counter(
        "vertical_service_requests_total",
        "Total HTTP requests.",
        ["route", "method", "status", "status_class"],
        registry=registry,
    )

    success_count = Counter(
        "vertical_service_success_total",
        "Total successful HTTP requests.",
        ["route", "method", "status", "status_class"],
        registry=registry,
    )

    failure_count = Counter(
        "vertical_service_failure_total",
        "Total failed HTTP requests.",
        ["route", "method", "status", "status_class", "error_kind"],
        registry=registry,
    )

    request_latency = Histogram(
        "vertical_service_request_latency_seconds",
        "HTTP request latency in seconds.",
        ["route", "method", "status", "status_class"],
        registry=registry,
    )

    @app.middleware("http")
    async def metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        route = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_label = "500"
            status_class = "5xx"
            request_count.labels(route=route, method=method, status=status_label, status_class=status_class).inc()
            failure_count.labels(
                route=route,
                method=method,
                status=status_label,
                status_class=status_class,
                error_kind="infrastructure",
            ).inc()
            request_latency.labels(route=route, method=method, status=status_label, status_class=status_class).observe(
                time.perf_counter() - start
            )
            raise

        status_label = str(status_code)
        status_class = f"{status_code // 100}xx"
        request_count.labels(route=route, method=method, status=status_label, status_class=status_class).inc()

        if status_code < HTTP_BAD_REQUEST:
            success_count.labels(route=route, method=method, status=status_label, status_class=status_class).inc()
        else:
            error_kind = "domain" if status_code < 500 else "infrastructure"
            failure_count.labels(
                route=route,
                method=method,
                status=status_label,
                status_class=status_class,
                error_kind=error_kind,
            ).inc()

        request_latency.labels(route=route, method=method, status=status_label, status_class=status_class).observe(
            time.perf_counter() - start
        )

        return response

    @app.get("/metrics", tags=["metrics"])
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return registry


# ---- Startup ----
def setup_startup(app: FastAPI) -> None:
    """Configure application startup as a lifespan handler."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        logger.info("Initializing application state")

        app.state.storage_client = create_storage_client()

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            msg = "Missing OPENAI_API_KEY"
            raise RuntimeError(msg)

        app.state.ai_client = get_ai_client()

        logger.info("Application state initialized")
        yield

    app.router.lifespan_context = lifespan


# ---- Routes ----
def setup_routes(app: FastAPI) -> None:
    """Register application startup event to initialize shared clients."""
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/auth", tags=["auth"])
    app.include_router(storage.router, prefix="/storage", tags=["storage"])
    app.include_router(agent.router, tags=["agent"])


# ---- App factory ----
def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="Cloud Storage Service",
        description="HTTP API for cloud storage with OAuth 2.0 authorization code flow.",
    )

    app.add_middleware(SessionMiddleware, secret_key=session_secret_key())

    setup_metrics(app)
    setup_startup(app)
    setup_routes(app)

    return app
