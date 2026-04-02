"""
Unit tests for:
  - app.core.token_store._RevocationStore  (access/refresh revocation)
  - app.core.token_store._LoginAttemptTracker (brute-force lockout)
  - app.core.log_filter._redact            (sensitive-data masking)
"""
import time
from datetime import datetime, timedelta, timezone

import pytest

from app.core.token_store import _RevocationStore, _LoginAttemptTracker
from app.core.log_filter import _redact


# ---------------------------------------------------------------------------
# _RevocationStore
# ---------------------------------------------------------------------------

class TestRevocationStore:
    def setup_method(self):
        self.store = _RevocationStore()

    def _future(self, seconds: int = 60) -> datetime:
        return datetime.now(timezone.utc) + timedelta(seconds=seconds)

    def _past(self, seconds: int = 1) -> datetime:
        return datetime.now(timezone.utc) - timedelta(seconds=seconds)

    def test_not_revoked_initially(self):
        assert self.store.is_revoked("some-jti") is False

    def test_revoke_marks_key(self):
        self.store.revoke("jti-abc", self._future())
        assert self.store.is_revoked("jti-abc") is True

    def test_different_key_not_revoked(self):
        self.store.revoke("jti-abc", self._future())
        assert self.store.is_revoked("jti-xyz") is False

    def test_expired_entry_is_not_revoked(self):
        # Revoke with a past expiry — already expired, so is_revoked must return False
        self.store.revoke("jti-old", self._past())
        assert self.store.is_revoked("jti-old") is False

    def test_len_excludes_expired(self):
        self.store.revoke("active", self._future(60))
        self.store.revoke("expired", self._past())
        assert len(self.store) == 1

    def test_prune_removes_expired_on_next_write(self):
        self.store.revoke("key1", self._past())
        self.store.revoke("key2", self._future())
        # Another write triggers _prune
        self.store.revoke("key3", self._future())
        assert not self.store.is_revoked("key1")

    def test_revoke_multiple_keys(self):
        for i in range(5):
            self.store.revoke(f"jti-{i}", self._future())
        assert len(self.store) == 5
        for i in range(5):
            assert self.store.is_revoked(f"jti-{i}") is True


# ---------------------------------------------------------------------------
# _LoginAttemptTracker
# ---------------------------------------------------------------------------

class TestLoginAttemptTracker:
    def setup_method(self):
        self.tracker = _LoginAttemptTracker()

    def test_not_locked_initially(self):
        locked, secs = self.tracker.is_locked("alice")
        assert locked is False
        assert secs is None

    def test_failure_increments_count(self):
        count = self.tracker.record_failure("alice")
        assert count == 1

    def test_four_failures_no_lockout(self):
        for _ in range(4):
            self.tracker.record_failure("alice")
        locked, _ = self.tracker.is_locked("alice")
        assert locked is False

    def test_five_failures_triggers_lockout(self):
        for _ in range(5):
            self.tracker.record_failure("alice")
        locked, secs = self.tracker.is_locked("alice")
        assert locked is True
        assert secs is not None
        assert secs > 800  # ~15 min

    def test_success_resets_counter(self):
        for _ in range(3):
            self.tracker.record_failure("bob")
        self.tracker.record_success("bob")
        locked, _ = self.tracker.is_locked("bob")
        assert locked is False
        # After reset, failures start from 0 again
        count = self.tracker.record_failure("bob")
        assert count == 1

    def test_different_users_isolated(self):
        for _ in range(5):
            self.tracker.record_failure("mallory")
        locked, _ = self.tracker.is_locked("alice")
        assert locked is False

    def test_lockout_expires(self):
        # Manually inject an already-expired lockout
        import threading
        self.tracker._lock = threading.Lock()
        self.tracker._attempts["expired_user"] = (5, time.time() - 1)
        locked, secs = self.tracker.is_locked("expired_user")
        assert locked is False
        assert secs is None


# ---------------------------------------------------------------------------
# Log filter redaction
# ---------------------------------------------------------------------------

class TestRedact:
    def test_bearer_token_redacted(self):
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.abc.def"
        result = _redact(msg)
        assert "eyJ" not in result
        assert "[REDACTED]" in result or "[JWT]" in result

    def test_api_key_header_redacted(self):
        msg = "X-Api-Key: sk_live_supersecretapikey"
        result = _redact(msg)
        assert "supersecretapikey" not in result

    def test_password_json_field_redacted(self):
        msg = '{"username": "alice", "password": "myS3cretP@ss"}'
        result = _redact(msg)
        assert "myS3cretP@ss" not in result
        assert "[REDACTED]" in result

    def test_fernet_ciphertext_redacted(self):
        # Fernet tokens start with gAAAA and are ~100+ base64 chars
        fake_fernet = "gAAAAA" + "A" * 80
        result = _redact(fake_fernet)
        assert "gAAAAA" not in result
        assert "[ENCRYPTED]" in result

    def test_sha256_hash_redacted(self):
        sha = "a" * 64  # 64 lowercase hex chars
        result = _redact(sha)
        assert "a" * 64 not in result
        assert "[HASH]" in result

    def test_jwt_three_segment_redacted(self):
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        result = _redact(jwt)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result

    def test_benign_text_unchanged(self):
        msg = "User alice logged in successfully from 127.0.0.1"
        result = _redact(msg)
        assert result == msg

    def test_hashed_password_field_redacted(self):
        msg = '{"hashed_password": "$argon2id$v=19$m=65536,t=3$longhashedvalue"}'
        result = _redact(msg)
        assert "$argon2id" not in result

    def test_refresh_token_field_redacted(self):
        msg = '{"refresh_token": "eyJhbGciOiJIUzI1NiJ9.abc.def"}'
        result = _redact(msg)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
