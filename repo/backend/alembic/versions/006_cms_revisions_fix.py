"""Fix CMS revision number constraint and extend revision snapshots.

The original CHECK (revision_number >= 1 AND revision_number <= 30) breaks
once a page accumulates more than 30 total saves (the numbers are sequential,
not reset).  The 30-revision cap is enforced at application layer by pruning
the oldest rows — not by a DB range constraint.

Also adds missing snapshot columns to cms_page_revisions so a rollback
can fully restore slug, locale, store_id, and SEO keywords.

Revision ID: 006_cms_revisions_fix
Revises: 005_threads_notifications
Create Date: 2024-01-06 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "006_cms_revisions_fix"
down_revision: Union[str, None] = "005_threads_notifications"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the overly-restrictive revision_number range constraint
    op.drop_constraint("ck_cms_revisions_number_range", "cms_page_revisions", type_="check")

    # Add >= 1 constraint only (no upper bound — pruning is at app layer)
    op.create_check_constraint(
        "ck_cms_revisions_number_positive",
        "cms_page_revisions",
        "revision_number >= 1",
    )

    # Extend revision snapshots for complete rollback
    op.add_column(
        "cms_page_revisions",
        sa.Column("slug_snapshot", sa.String(500), nullable=True),
    )
    op.add_column(
        "cms_page_revisions",
        sa.Column("store_id_snapshot", sa.String(100), nullable=True),
    )
    op.add_column(
        "cms_page_revisions",
        sa.Column("locale_snapshot", sa.String(10), nullable=True),
    )
    op.add_column(
        "cms_page_revisions",
        sa.Column("seo_keywords_snapshot", sa.Text, nullable=True),
    )
    op.add_column(
        "cms_page_revisions",
        sa.Column("sitemap_priority_snapshot", sa.Numeric(2, 1), nullable=True),
    )
    op.add_column(
        "cms_page_revisions",
        sa.Column("sitemap_changefreq_snapshot", sa.String(20), nullable=True),
    )
    op.add_column(
        "cms_page_revisions",
        sa.Column("is_in_sitemap_snapshot", sa.Boolean, nullable=True),
    )

    # Index for fast revision listing by page + number
    op.create_index(
        "ix_cms_page_revisions_page_rev",
        "cms_page_revisions",
        ["page_id", "revision_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_cms_page_revisions_page_rev", table_name="cms_page_revisions")
    for col in [
        "slug_snapshot", "store_id_snapshot", "locale_snapshot",
        "seo_keywords_snapshot", "sitemap_priority_snapshot",
        "sitemap_changefreq_snapshot", "is_in_sitemap_snapshot",
    ]:
        op.drop_column("cms_page_revisions", col)
    op.drop_constraint("ck_cms_revisions_number_positive", "cms_page_revisions", type_="check")
    op.create_check_constraint(
        "ck_cms_revisions_number_range",
        "cms_page_revisions",
        "revision_number >= 1 AND revision_number <= 30",
    )
