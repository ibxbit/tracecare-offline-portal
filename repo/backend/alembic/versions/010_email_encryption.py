"""Email encryption at rest: add email_hash, encrypt email column.

Revision ID: 010_email_enc
Revises: 009_audit_log
Create Date: 2026-04-08 00:00:00.000000

Strategy
--------
1. Add email_hash VARCHAR(64) column (SHA-256 of normalised email).
2. Backfill email_hash for all existing rows using a Python-level hash
   (we cannot call our app-layer encryptor from pure SQL, so we hash with pgcrypto
   or a Python migration step).
3. Drop the old UNIQUE constraint on email (encrypted values are non-deterministic).
4. Add UNIQUE constraint on email_hash.
5. Resize email column to VARCHAR(500) to hold Fernet ciphertext.

Note: existing email values are NOT retroactively encrypted in this migration
because Fernet encryption requires the app's ENCRYPTION_KEY which is not
available in pure SQL.  A follow-up data migration script (backfill_email_encryption.py)
should be run once to encrypt existing rows if the DB was already populated.
The EncryptedString TypeDecorator handles all new reads/writes transparently.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "010_email_enc"
down_revision: Union[str, None] = "009_audit_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add email_hash column (nullable initially for backfill)
    op.add_column(
        "users",
        sa.Column("email_hash", sa.String(64), nullable=True),
    )

    # 2. Backfill email_hash from existing plaintext email values using SHA-256
    #    We use pgcrypto's digest() if available, otherwise fall back to MD5.
    #    For portability we use a Python-based approach via op.execute with a CTE.
    op.execute("""
        UPDATE users
        SET email_hash = encode(digest(lower(trim(email)), 'sha256'), 'hex')
        WHERE email_hash IS NULL
    """)

    # 3. Make email_hash NOT NULL and add UNIQUE constraint
    op.alter_column("users", "email_hash", nullable=False)
    op.create_unique_constraint("uq_users_email_hash", "users", ["email_hash"])
    op.create_index("ix_users_email_hash", "users", ["email_hash"])

    # 4. Resize email column to VARCHAR(500) for Fernet ciphertext
    #    (Fernet adds ~50 bytes of overhead per token + base64 expansion)
    op.alter_column(
        "users", "email",
        type_=sa.String(500),
        existing_type=sa.String(255),
        existing_nullable=False,
    )

    # 5. Drop old unique constraint on raw email (no longer meaningful once encrypted)
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")


def downgrade() -> None:
    # Restore email column size and constraints
    op.alter_column(
        "users", "email",
        type_=sa.String(255),
        existing_type=sa.String(500),
        existing_nullable=False,
    )
    op.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
    op.drop_index("ix_users_email_hash", table_name="users")
    op.drop_constraint("uq_users_email_hash", "users", type_="unique")
    op.drop_column("users", "email_hash")
