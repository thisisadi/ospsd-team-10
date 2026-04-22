"""Names and copy for the optional ``/agent`` API key guard (service-to-service auth)."""

from __future__ import annotations

ENV_AGENT_API_KEY = "AGENT_API_KEY"
HTTP_HEADER_X_API_KEY = "X-API-Key"
MSG_INVALID_OR_MISSING_KEY = "Invalid or missing X-API-Key header. Provide the shared key configured in AGENT_API_KEY."
MSG_SERVER_AGENT_KEY_UNSET = "Server is not configured: set AGENT_API_KEY in the service environment to enable agent invocations."
