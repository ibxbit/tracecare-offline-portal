"""Logging filter that redacts sensitive values before they reach any log sink.

Patterns redacted:
  • Authorization: Bearer <token>   → Authorization: Bearer [REDACTED]
  • X-Api-Key: <value>              → X-Api-Key: [REDACTED]
  • "password": "..."               → "password": "[REDACTED]"
  • "hashed_password": "..."        → "hashed_password": "[REDACTED]"
  • "refresh_token": "..."          → "refresh_token": "[REDACTED]"
  • "access_token": "..."           → "access_token": "[REDACTED]"
  • Fernet ciphertext (gAAAA... 80+ chars) → [ENCRYPTED]
  • SHA-256 hex digests in logs     → [HASH]
"""
from __future__ import annotations

import logging
import re

# Patterns: (compiled_regex, replacement_string)
_PATTERNS: list[tuple[re.Pattern, str]] = [
    # HTTP Authorization header value
    (re.compile(r"(Authorization:\s*Bearer\s+)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    (re.compile(r"(X-Api-Key:\s*)\S+", re.IGNORECASE), r"\1[REDACTED]"),
    # JSON / form field values
    (re.compile(r'("(?:password|hashed_password|refresh_token|access_token|session_token_hash|key_hash|password_encrypted)"\s*:\s*)"[^"]{4,}"', re.IGNORECASE), r'\1"[REDACTED]"'),
    # URL-encoded login fields
    (re.compile(r"(password=)[^&\s]+", re.IGNORECASE), r"\1[REDACTED]"),
    # Fernet ciphertext: starts with gAAAA, typically 80+ base64 chars
    (re.compile(r"gAAAA[A-Za-z0-9+/=]{75,}"), "[ENCRYPTED]"),
    # SHA-256 hex digests (64 lowercase hex chars)
    (re.compile(r"\b[0-9a-f]{64}\b"), "[HASH]"),
    # JWT tokens (three base64url segments)
    (re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"), "[JWT]"),
]


def _redact(text: str) -> str:
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SensitiveDataFilter(logging.Filter):
    """Attach to any logging.Handler to scrub sensitive values from records."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        # Redact the formatted message and the raw args
        try:
            record.msg = _redact(str(record.msg))
            if isinstance(record.args, dict):
                record.args = {k: _redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, (list, tuple)):
                record.args = type(record.args)(_redact(str(a)) for a in record.args)
        except Exception:
            pass  # Never let the filter break log emission
        return True


def configure_secure_logging() -> None:
    """Install the redaction filter on the root logger and uvicorn access logger."""
    filt = SensitiveDataFilter()
    for name in ("", "uvicorn", "uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        handler_logger = logging.getLogger(name)
        # Attach to all existing handlers
        for handler in handler_logger.handlers:
            if not any(isinstance(f, SensitiveDataFilter) for f in handler.filters):
                handler.addFilter(filt)
        # Also attach to the logger itself (catches handlers added later)
        if not any(isinstance(f, SensitiveDataFilter) for f in handler_logger.filters):
            handler_logger.addFilter(filt)
