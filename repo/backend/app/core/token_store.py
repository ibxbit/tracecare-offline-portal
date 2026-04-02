"""Thread-safe in-memory token revocation store.

Tracks both access tokens (by jti) and refresh tokens (by raw value).
Expired entries are pruned lazily on each lookup — no background thread needed.

Design constraints (offline/single-process):
  - No Redis. All state lives in the process.
  - Process restarts clear the store, which is acceptable because:
      * Access tokens expire in 15 min anyway.
      * Refresh tokens expire in 12 h anyway.
      * On restart, clients will re-authenticate.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone


class _RevocationStore:
    """
    Stores (token_key -> unix_expiry_timestamp) mappings.
    Keys that have passed their expiry are silently ignored on lookup
    and pruned on the next write.
    """

    def __init__(self) -> None:
        self._store: dict[str, float] = {}
        self._lock = threading.Lock()

    def revoke(self, key: str, expires_at: datetime) -> None:
        """Mark *key* as revoked until *expires_at* (tz-aware UTC)."""
        ts = expires_at.timestamp()
        with self._lock:
            self._prune()
            self._store[key] = ts

    def is_revoked(self, key: str) -> bool:
        """Return True if *key* is in the revocation list and has not expired."""
        now = time.time()
        with self._lock:
            ts = self._store.get(key)
            if ts is None:
                return False
            if now >= ts:
                # Token's own expiry has passed; no longer relevant.
                del self._store[key]
                return False
            return True

    def _prune(self) -> None:
        """Remove all expired entries (call with lock held)."""
        now = time.time()
        expired = [k for k, ts in self._store.items() if now >= ts]
        for k in expired:
            del self._store[k]

    def __len__(self) -> int:
        with self._lock:
            self._prune()
            return len(self._store)


# Singleton stores — imported everywhere
access_token_store = _RevocationStore()   # keyed by jti (UUID)
refresh_token_store = _RevocationStore()  # keyed by raw token string


# ---------------------------------------------------------------------------
# Login-attempt rate limiting (per username, in-memory)
# ---------------------------------------------------------------------------

_MAX_ATTEMPTS = 5          # failures before lockout
_LOCKOUT_SECONDS = 900     # 15 minutes

class _LoginAttemptTracker:
    """Track consecutive failed login attempts per username."""

    def __init__(self) -> None:
        # username -> (consecutive_failures, locked_until_timestamp | None)
        self._attempts: dict[str, tuple[int, float | None]] = {}
        self._lock = threading.Lock()

    def record_failure(self, username: str) -> int:
        """Increment failure counter. Returns the new count."""
        with self._lock:
            failures, locked_until = self._attempts.get(username, (0, None))
            failures += 1
            locked_until = time.time() + _LOCKOUT_SECONDS if failures >= _MAX_ATTEMPTS else locked_until
            self._attempts[username] = (failures, locked_until)
            return failures

    def record_success(self, username: str) -> None:
        """Reset counter on successful login."""
        with self._lock:
            self._attempts.pop(username, None)

    def is_locked(self, username: str) -> tuple[bool, float | None]:
        """Return (is_locked, seconds_remaining) for *username*."""
        with self._lock:
            failures, locked_until = self._attempts.get(username, (0, None))
            if locked_until is None:
                return False, None
            remaining = locked_until - time.time()
            if remaining <= 0:
                # Lockout expired — reset
                self._attempts.pop(username, None)
                return False, None
            return True, remaining


login_attempt_tracker = _LoginAttemptTracker()
