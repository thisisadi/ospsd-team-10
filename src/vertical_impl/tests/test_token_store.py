from datetime import UTC, datetime, timedelta

from vertical_impl.token_store import (
    TokenData,
    delete_token,
    get_token,
    is_token_expired,
    store_token,
)


def test_store_and_get_token() -> None:
    token = TokenData(
        access_token="access",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
        refresh_token="refresh",
        scope="read write",
    )

    store_token("session-1", token)

    assert get_token("session-1") == token


def test_delete_token_removes_entry() -> None:
    token = TokenData(
        access_token="access",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )

    store_token("session-2", token)
    delete_token("session-2")

    assert get_token("session-2") is None


def test_delete_token_missing_session_is_safe() -> None:
    delete_token("does-not-exist")
    assert get_token("does-not-exist") is None


def test_is_token_expired_false_when_no_expiry() -> None:
    token = TokenData(
        access_token="access",
        token_type="Bearer",
        expires_at=None,
    )

    assert is_token_expired(token) is False


def test_is_token_expired_true_for_past_expiry() -> None:
    token = TokenData(
        access_token="access",
        token_type="Bearer",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    assert is_token_expired(token) is True


def test_is_token_expired_false_for_future_expiry_outside_skew() -> None:
    token = TokenData(
        access_token="access",
        token_type="Bearer",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    assert is_token_expired(token) is False