"""FastAPI application factory and configuration."""

import logging
import os
import time
from collections.abc import Awaitable, Callable

from ai_client_api.client import get_ai_client
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
from vertical_service.config import session_secret_key
from vertical_service.provider_switching.factory import create_storage_client
from vertical_service.routes import agent, auth, health, storage

logger = logging.getLogger(__name__)
HTTP_BAD_REQUEST = 400
HTTP_INTERNAL_ERROR = 500


def _status_class(status_code: int) -> str:
    """Map HTTP status to Prometheus ``status_class`` label."""
    if status_code < HTTP_BAD_REQUEST:
        return "ok"
    if status_code < HTTP_INTERNAL_ERROR:
        return "domain_error"
    return "infra_error"


# ---- Metrics setup ----
def setup_metrics(app: FastAPI) -> CollectorRegistry:
    """Configure Prometheus metrics and attach middleware to the app."""
    registry = CollectorRegistry()

    request_count = Counter(
        "vertical_service_requests_total",
        "Total HTTP requests.",
        ["endpoint", "method"],
        registry=registry,
    )

    success_count = Counter(
        "vertical_service_success_total",
        "Total successful HTTP requests.",
        ["endpoint", "method", "status_class"],
        registry=registry,
    )

    failure_count = Counter(
        "vertical_service_failure_total",
        "Total failed HTTP requests.",
        ["endpoint", "method", "status_class"],
        registry=registry,
    )

    request_latency = Histogram(
        "vertical_service_request_latency_seconds",
        "HTTP request latency in seconds.",
        ["endpoint", "method", "status_class"],
        registry=registry,
    )

    @app.middleware("http")
    async def metrics_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        endpoint = request.url.path
        method = request.method

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            request_count.labels(endpoint=endpoint, method=method).inc()
            failure_count.labels(endpoint=endpoint, method=method, status_class="infra_error").inc()
            request_latency.labels(endpoint=endpoint, method=method, status_class="infra_error").observe(
                time.perf_counter() - start,
            )
            raise

        request_count.labels(endpoint=endpoint, method=method).inc()

        sc = _status_class(status_code)
        request_latency.labels(endpoint=endpoint, method=method, status_class=sc).observe(time.perf_counter() - start)

        if status_code < HTTP_BAD_REQUEST:
            success_count.labels(endpoint=endpoint, method=method, status_class="ok").inc()
        else:
            failure_sc = "domain_error" if status_code < HTTP_INTERNAL_ERROR else "infra_error"
            failure_count.labels(endpoint=endpoint, method=method, status_class=failure_sc).inc()

        return response

    @app.get("/metrics", tags=["metrics"])
    def metrics() -> Response:
        return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

    return registry


# ---- Startup ----
def setup_startup(app: FastAPI) -> None:
    """Configure Prometheus metrics and attach middleware to the app."""

    @app.on_event("startup")
    def startup() -> None:
        logger.info("Initializing application state")

        app.state.storage_client = create_storage_client()

        if not os.environ.get("OPENAI_API_KEY"):
            msg = "Missing OPENAI_API_KEY"
            raise RuntimeError(msg)

        app.state.ai_client = get_ai_client()

        logger.info("Application state initialized")


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
