"""Environment variable names and operator-facing error text (no inline magic strings)."""

from __future__ import annotations

ENV_CHAT_SERVICE_BASE_URL = "CHAT_SERVICE_BASE_URL"
ENV_CHAT_SESSION_ID = "CHAT_SESSION_ID"

MSG_MISSING_BASE = (
    f"{ENV_CHAT_SERVICE_BASE_URL} must be set to the base URL of the Team 9 chat service (no trailing slash)."
)
MSG_MISSING_SESSION = (
    f"{ENV_CHAT_SESSION_ID} must be set to a valid OAuth session id from the Team 9 service "
    "(/auth/sessions). Sessions are in-memory and reset when their server restarts; obtain a new id and update env."
)
MSG_AUTH_SESSION = (
    "The Team 9 chat service rejected the session id. Complete Slack OAuth again via Team 9's /auth/sessions, "
    "update the in-memory session id in your environment, and retry. If the service restarted, all sessions were lost."
)
MSG_UNEXPECTED_SEND = "Unexpected response while sending a message to the Team 9 chat service."
MSG_VALIDATION = "The Team 9 chat service rejected the request body (validation error)."
MSG_NETWORK = "Network error while calling the Team 9 chat service."
MSG_NO_MESSAGE_ID = "The Team 9 chat service did not return a message id in the success response payload."
