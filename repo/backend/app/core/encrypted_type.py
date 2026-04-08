"""
EncryptedString — SQLAlchemy TypeDecorator for Fernet-encrypted text columns.

Usage
-----
    email: Mapped[str] = mapped_column(EncryptedString(500), nullable=False)

The column stores Fernet ciphertext (base64url-encoded).
Python-side reads transparently decrypt; writes transparently encrypt.

For uniqueness lookups (e.g. "does this email already exist?") use the
companion `email_hash` column (SHA-256 of the normalised plaintext).
"""
from __future__ import annotations

import hashlib

from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

from app.core.encryption import encryptor


class EncryptedString(TypeDecorator):
    """Store strings as Fernet-encrypted ciphertext; decrypt on load."""

    impl = String
    cache_ok = True

    def __init__(self, length: int = 500, *args, **kwargs):
        # The encrypted ciphertext is longer than plaintext; allocate extra.
        super().__init__(length, *args, **kwargs)

    def process_bind_param(self, value, dialect):
        """Encrypt before writing to DB."""
        if value is None:
            return None
        return encryptor.encrypt(str(value))

    def process_result_value(self, value, dialect):
        """Decrypt after reading from DB."""
        if value is None:
            return None
        try:
            return encryptor.decrypt(value)
        except Exception:
            # Return the raw value so existing plaintext rows don't break
            # during a rolling migration (they won't look like valid Fernet tokens).
            return value


def email_hash(email: str) -> str:
    """Return the SHA-256 hex digest of the normalised email for lookup."""
    normalised = email.strip().lower()
    return hashlib.sha256(normalised.encode()).hexdigest()
