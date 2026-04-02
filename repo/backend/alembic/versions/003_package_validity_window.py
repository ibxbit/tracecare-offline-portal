"""Add validity_window_days to packages and tighten constraints.

Revision ID: 003_package_validity
Revises: 002_extended
Create Date: 2024-01-03 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "003_package_validity"
down_revision: Union[str, None] = "002_extended"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add validity_window_days column to packages
    op.add_column(
        "packages",
        sa.Column("validity_window_days", sa.Integer, nullable=True),
    )

    # Flip is_active default from true to false — new versions start inactive
    # (no server_default change needed; existing rows remain as-is)

    # Add CHECK constraints to packages
    op.create_check_constraint(
        "ck_packages_price_non_negative", "packages", "price >= 0"
    )
    op.create_check_constraint(
        "ck_packages_validity_positive",
        "packages",
        "validity_window_days IS NULL OR validity_window_days > 0",
    )

    # Add index on packages.name for version-history queries
    op.create_index("ix_packages_name", "packages", ["name"])


def downgrade() -> None:
    op.drop_index("ix_packages_name", table_name="packages")
    op.drop_constraint("ck_packages_validity_positive", "packages", type_="check")
    op.drop_constraint("ck_packages_price_non_negative", "packages", type_="check")
    op.drop_column("packages", "validity_window_days")
