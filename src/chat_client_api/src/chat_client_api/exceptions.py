"""Exception types for the chat client port boundary."""


class ChatServiceError(Exception):
    """Base error for failures when calling the external chat (Team 9) service."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
    ) -> None:
        """Store a user-facing message and optional HTTP status from the remote service."""
        super().__init__(message)
        self.status_code: int | None = status_code


class ChatServiceAuthError(ChatServiceError):
    """Raised when the remote chat service rejected the session (e.g. unknown or expired OAuth session)."""

    def __init__(self, message: str) -> None:
        """Build an auth error with a clear, actionable message for operators."""
        super().__init__(message, status_code=401)
