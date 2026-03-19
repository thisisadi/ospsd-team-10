"""Adapter layer to expose service usage through the original interface."""

from __future__ import annotations

from vertical_api.client import register_client_factory

from vertical_adapter.adapter import CloudStorageServiceAdapter


def register() -> None:
    """Register the HTTP service adapter as the active :class:`vertical_api.client.Client` implementation."""
    register_client_factory(CloudStorageServiceAdapter)


__all__ = ["CloudStorageServiceAdapter", "register"]
