"""Add page_type column to cms_pages.

Revision ID: 007_cms_page_type
Revises: 006_cms_revisions_fix
Create Date: 2024-01-07 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "007_cms_page_type"
down_revision: Union[str, None] = "006_cms_revisions_fix"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "cms_pages",
        sa.Column("page_type", sa.String(50), nullable=True),
    )
    op.create_index("ix_cms_pages_page_type", "cms_pages", ["page_type"])


def downgrade() -> None:
    op.drop_index("ix_cms_pages_page_type", table_name="cms_pages")
    op.drop_column("cms_pages", "page_type")
