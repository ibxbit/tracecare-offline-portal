"""Drop the global unique constraint on cms_pages.slug.

Revision ID: 012_cms_slug_per_store_locale
Revises: 011_catalog_tags_priority
Create Date: 2026-04-15 00:00:00.000000

Why
---
The initial schema (001) declared `cms_pages.slug` as globally UNIQUE, but
migration 002 introduced a composite `uq_cms_pages_slug_store_locale`
uniqueness constraint over (slug, store_id, locale). The two constraints
are contradictory: the composite constraint permits multi-store and
multi-locale variants that share a slug, but the global unique index
blocks them.

The application layer (`_check_slug_unique`) already enforces uniqueness
within the (slug, store_id, locale) tuple, so the composite constraint is
the correct one. This migration drops the global unique index so slugs
can legitimately recur across store/locale variants — which is required
to support multi-store and multilingual CMS content.
"""
from typing import Sequence, Union

from alembic import op


revision: str = "012_cms_slug_per_store_locale"
down_revision: Union[str, None] = "011_catalog_tags_priority"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the global unique constraint/index on slug, replace with a plain index.
    # Postgres creates the unique index with the same name the SQLAlchemy
    # column generated: ix_cms_pages_slug.
    op.execute("DROP INDEX IF EXISTS ix_cms_pages_slug")
    op.create_index("ix_cms_pages_slug", "cms_pages", ["slug"], unique=False)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cms_pages_slug")
    op.create_index("ix_cms_pages_slug", "cms_pages", ["slug"], unique=True)
