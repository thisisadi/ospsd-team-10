"""Prometheus metrics for vertical service."""

from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "vertical_service_requests_total",
    "Total number of requests",
    ["endpoint", "method"],
)

SUCCESS_COUNT = Counter(
    "vertical_service_success_total",
    "Total successful requests",
    ["endpoint", "method"],
)

FAILURE_COUNT = Counter(
    "vertical_service_failure_total",
    "Total failed requests",
    ["endpoint", "method"],
)

REQUEST_LATENCY = Histogram(
    "vertical_service_request_latency_seconds",
    "Request latency in seconds",
    ["endpoint", "method"],
)
