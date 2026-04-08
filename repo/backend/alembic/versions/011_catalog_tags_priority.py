"""Add tags and priority columns to catalog_items.

Revision ID: 011_catalog_tags_priority
Revises: 010_email_enc
Create Date: 2026-04-08 00:00:00.000000

Changes
-------
- catalog_items.tags TEXT nullable  — comma-separated keyword tags
- catalog_items.priority INTEGER nullable (1–5) — priority level with CHECK constraint
  Existing rows default to NULL (unset); no data migration required.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "011_catalog_tags_priority"
down_revision: Union[str, None] = "010_email_enc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add tags column — nullable, no default (existing rows get NULL)
    op.add_column(
        "catalog_items",
        sa.Column("tags", sa.Text(), nullable=True),
    )

    # Add priority column — nullable integer 1-5
    op.add_column(
        "catalog_items",
        sa.Column("priority", sa.Integer(), nullable=True),
    )

    # Enforce 1-5 range at DB level (application layer also validates)
    op.create_check_constraint(
        "ck_catalog_items_priority_range",
        "catalog_items",
        "priority IS NULL OR (priority >= 1 AND priority <= 5)",
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE catalog_items DROP CONSTRAINT IF EXISTS ck_catalog_items_priority_range"
    )
    op.drop_column("catalog_items", "priority")
    op.drop_column("catalog_items", "tags")
