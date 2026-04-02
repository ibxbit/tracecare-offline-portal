"""Add moderation, credibility, and store fields to reviews table.

Revision ID: 004_review_moderation
Revises: 003_package_validity
Create Date: 2024-01-04 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "004_review_moderation"
down_revision: Union[str, None] = "003_package_validity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Credibility score — persisted float [0.000, 1.000]
    op.add_column(
        "reviews",
        sa.Column("credibility_score", sa.Numeric(4, 3), nullable=False, server_default="0.000"),
    )

    # Moderation flags
    op.add_column(
        "reviews",
        sa.Column("is_pinned", sa.Boolean, nullable=False, server_default="false"),
    )
    op.add_column(
        "reviews",
        sa.Column("is_collapsed", sa.Boolean, nullable=False, server_default="false"),
    )

    # Per-store scope
    op.add_column(
        "reviews",
        sa.Column("store_id", sa.String(100), nullable=False, server_default="default"),
    )

    # Moderator identity & audit trail
    op.add_column(
        "reviews",
        sa.Column("moderation_note", sa.String(500), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("moderated_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
    )
    op.add_column(
        "reviews",
        sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes for common queries
    op.create_index("ix_reviews_is_pinned", "reviews", ["is_pinned"])
    op.create_index("ix_reviews_store_id", "reviews", ["store_id"])
    op.create_index("ix_reviews_credibility_score", "reviews", ["credibility_score"])

    # Constraints
    op.create_check_constraint(
        "ck_reviews_credibility_range",
        "reviews",
        "credibility_score >= 0.0 AND credibility_score <= 1.0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_reviews_credibility_range", "reviews", type_="check")
    op.drop_index("ix_reviews_credibility_score", table_name="reviews")
    op.drop_index("ix_reviews_store_id", table_name="reviews")
    op.drop_index("ix_reviews_is_pinned", table_name="reviews")
    op.drop_column("reviews", "moderated_at")
    op.drop_column("reviews", "moderated_by")
    op.drop_column("reviews", "moderation_note")
    op.drop_column("reviews", "store_id")
    op.drop_column("reviews", "is_collapsed")
    op.drop_column("reviews", "is_pinned")
    op.drop_column("reviews", "credibility_score")
