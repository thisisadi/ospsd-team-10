"""Minimal typed HTTP client for service API calls."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass(slots=True)
class RequestOptions:
    """Optional request values used by ApiClient.request."""

    params: dict[str, str] | None = None
    content: bytes | None = None
    json_body: dict[str, object] | None = None
    extra_headers: dict[str, str] | None = None


@dataclass(slots=True)
class ApiClient:
    """Shared HTTP client configuration for service endpoints."""

    base_url: str
    timeout_seconds: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)

    def build_url(self, path: str) -> str:
        """Return absolute URL for a path."""
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def request(self, method: str, path: str, options: RequestOptions | None = None) -> httpx.Response:
        """Execute one request and raise on non-success status."""
        request_options = options or RequestOptions()
        merged_headers: dict[str, str] = {}
        merged_headers.update(self.headers)
        if request_options.extra_headers is not None:
            merged_headers.update(request_options.extra_headers)

        response = httpx.request(
            method=method,
            url=self.build_url(path),
            timeout=self.timeout_seconds,
            headers=merged_headers,
            params=request_options.params,
            content=request_options.content,
            json=request_options.json_body,
        )
        response.raise_for_status()
        return response
