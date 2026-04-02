"""Initial schema

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column(
            "role",
            sa.Enum("admin", "clinic_staff", "catalog_manager", "end_user", name="userrole"),
            nullable=False,
            server_default="end_user",
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Exams table
    op.create_table(
        "exams",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("patient_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("staff_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("exam_type", sa.String(200), nullable=False),
        sa.Column("findings_encrypted", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.Enum("scheduled", "in_progress", "completed", "cancelled", name="examstatus"),
            nullable=False,
            server_default="scheduled",
        ),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Products table
    op.create_table(
        "products",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sku", sa.String(100), unique=True, nullable=False, index=True),
        sa.Column("origin", sa.String(255), nullable=True),
        sa.Column("batch_number", sa.String(100), nullable=True),
        sa.Column("harvest_date", sa.Date, nullable=True),
        sa.Column("processing_date", sa.Date, nullable=True),
        sa.Column("expiry_date", sa.Date, nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Trace Events table
    op.create_table(
        "trace_events",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("harvested", "processed", "packaged", "shipped", "received", name="traceeventtype"),
            nullable=False,
        ),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("operator_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Catalog Items table
    op.create_table(
        "catalog_items",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("stock_quantity", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Messages table
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("sender_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("body_encrypted", sa.Text, nullable=False),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # CMS Pages table
    op.create_table(
        "cms_pages",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), unique=True, nullable=False, index=True),
        sa.Column("content", sa.Text, nullable=False, server_default=""),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # Reviews table
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "subject_type",
            sa.Enum("product", "exam_type", name="reviewsubjecttype"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.Integer, nullable=True),
        sa.Column("subject_text", sa.String(255), nullable=True),
        sa.Column("reviewer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("cms_pages")
    op.drop_table("messages")
    op.drop_table("catalog_items")
    op.drop_table("trace_events")
    op.drop_table("products")
    op.drop_table("exams")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS reviewsubjecttype")
    op.execute("DROP TYPE IF EXISTS traceeventtype")
    op.execute("DROP TYPE IF EXISTS examstatus")
    op.execute("DROP TYPE IF EXISTS userrole")
