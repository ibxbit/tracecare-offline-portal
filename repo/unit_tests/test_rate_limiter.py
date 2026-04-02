"""
Unit tests for app.core.rate_limiter (sliding-window, in-memory, no Redis).
"""
import time

import pytest

from app.core.rate_limiter import check_rate_limit, current_usage, reset_key


def _unique_key(prefix: str = "test") -> str:
    """Return a key that doesn't share state with other tests."""
    import uuid
    return f"{prefix}_{uuid.uuid4().hex}"


class TestCheckRateLimit:
    def test_first_request_allowed(self):
        key = _unique_key()
        assert check_rate_limit(key, limit=10) is True

    def test_requests_up_to_limit_allowed(self):
        key = _unique_key()
        for _ in range(5):
            assert check_rate_limit(key, limit=5) is True

    def test_request_over_limit_denied(self):
        key = _unique_key()
        for _ in range(5):
            check_rate_limit(key, limit=5)
        # 6th request should be denied
        assert check_rate_limit(key, limit=5) is False

    def test_limit_of_one(self):
        key = _unique_key()
        assert check_rate_limit(key, limit=1) is True
        assert check_rate_limit(key, limit=1) is False

    def test_different_keys_independent(self):
        key_a = _unique_key("a")
        key_b = _unique_key("b")
        for _ in range(3):
            check_rate_limit(key_a, limit=3)
        # key_b should still be allowed
        assert check_rate_limit(key_b, limit=3) is True

    def test_window_expiry_allows_new_requests(self):
        key = _unique_key()
        # Fill up the limit in a very short window (1 second)
        for _ in range(3):
            check_rate_limit(key, limit=3, window_seconds=1)
        assert check_rate_limit(key, limit=3, window_seconds=1) is False

        # Wait for the window to expire
        time.sleep(1.1)
        assert check_rate_limit(key, limit=3, window_seconds=1) is True


class TestCurrentUsage:
    def test_zero_before_any_request(self):
        key = _unique_key()
        assert current_usage(key) == 0

    def test_counts_recorded_requests(self):
        key = _unique_key()
        for _ in range(4):
            check_rate_limit(key, limit=100)
        assert current_usage(key) == 4

    def test_does_not_increment_on_read(self):
        key = _unique_key()
        check_rate_limit(key, limit=100)
        before = current_usage(key)
        current_usage(key)
        after = current_usage(key)
        assert before == after == 1

    def test_expired_entries_excluded(self):
        key = _unique_key()
        for _ in range(3):
            check_rate_limit(key, limit=100, window_seconds=1)
        time.sleep(1.1)
        assert current_usage(key, window_seconds=1) == 0


class TestResetKey:
    def test_reset_clears_counter(self):
        key = _unique_key()
        for _ in range(5):
            check_rate_limit(key, limit=10)
        assert current_usage(key) == 5
        reset_key(key)
        assert current_usage(key) == 0

    def test_reset_allows_requests_again(self):
        key = _unique_key()
        for _ in range(3):
            check_rate_limit(key, limit=3)
        assert check_rate_limit(key, limit=3) is False
        reset_key(key)
        assert check_rate_limit(key, limit=3) is True

    def test_reset_nonexistent_key_no_error(self):
        reset_key("key-that-never-existed")  # should not raise

    def test_reset_only_affects_target_key(self):
        key_a = _unique_key("a")
        key_b = _unique_key("b")
        for _ in range(5):
            check_rate_limit(key_a, limit=10)
            check_rate_limit(key_b, limit=10)
        reset_key(key_a)
        assert current_usage(key_a) == 0
        assert current_usage(key_b) == 5
