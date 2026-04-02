"""In-memory sliding-window rate limiter for per-API-key enforcement.

Designed for offline/on-prem use — no Redis required.
The window resets if the process restarts, which is acceptable for local deployments.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


# Global window store: key_hash → deque of monotonic timestamps
_windows: dict[str, deque[float]] = defaultdict(deque)
_lock = threading.Lock()


def check_rate_limit(key: str, limit: int, window_seconds: int = 60) -> bool:
    """Return True (allow) or False (deny) for the given key.

    Prunes timestamps older than *window_seconds*, then checks count vs *limit*.
    If allowed, records the current timestamp before returning.
    """
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        dq = _windows[key]
        # Evict expired entries
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= limit:
            return False
        dq.append(now)
        return True


def current_usage(key: str, window_seconds: int = 60) -> int:
    """Return the number of requests in the current window (read-only)."""
    now = time.monotonic()
    cutoff = now - window_seconds
    with _lock:
        dq = _windows[key]
        while dq and dq[0] < cutoff:
            dq.popleft()
        return len(dq)


def reset_key(key: str) -> None:
    """Clear all timestamps for a key (e.g. after rotation)."""
    with _lock:
        _windows.pop(key, None)
