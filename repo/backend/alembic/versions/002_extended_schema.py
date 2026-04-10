"""Extended schema: exam items, packages, orders, notifications, CMS revisions,
   review images, catalog attachments, user session fields.

Revision ID: 002_extended
Revises: 001_initial
Create Date: 2024-01-02 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_extended"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # ------------------------------------------------------------------
    # 1. Extend users table
    # ------------------------------------------------------------------
    op.add_column("users", sa.Column("last_login", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("session_token_hash", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("session_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("failed_login_attempts", sa.Integer, nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("updated_at", sa.DateTime(timezone=True),
                                     nullable=False, server_default=sa.func.now()))

    # ------------------------------------------------------------------
    # 2. Exam items dictionary
    # ------------------------------------------------------------------
    op.create_table(
        "exam_items",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("code", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("ref_range_min", sa.Numeric(12, 4), nullable=True),
        sa.Column("ref_range_max", sa.Numeric(12, 4), nullable=True),
        sa.Column("ref_range_text", sa.String(255), nullable=True),
        sa.Column(
            "applicable_sex",
            sa.Enum("male", "female", "all", name="examitemsex"),
            nullable=False,
            server_default="all",
        ),
        sa.Column("min_age_years", sa.Integer, nullable=True),
        sa.Column("max_age_years", sa.Integer, nullable=True),
        sa.Column("contraindications", sa.Text, nullable=True),
        sa.Column("collection_method", sa.String(255), nullable=True),
        sa.Column("preparation_instructions", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "(ref_range_min IS NULL OR ref_range_max IS NULL) OR ref_range_min <= ref_range_max",
            name="ck_exam_items_ref_range_order",
        ),
        sa.CheckConstraint(
            "(min_age_years IS NULL OR max_age_years IS NULL) OR min_age_years <= max_age_years",
            name="ck_exam_items_age_range_order",
        ),
    )

    # ------------------------------------------------------------------
    # 3. Packages (versioned bundles)
    # ------------------------------------------------------------------
    op.create_table(
        "packages",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("price", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name", "version", name="uq_packages_name_version"),
    )

    op.create_table(
        "package_items",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("package_id", sa.Integer, sa.ForeignKey("packages.id"), nullable=False),
        sa.Column("exam_item_id", sa.Integer, sa.ForeignKey("exam_items.id"), nullable=False),
        sa.Column("is_required", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("item_code_snapshot", sa.String(50), nullable=False),
        sa.Column("item_name_snapshot", sa.String(255), nullable=False),
        sa.Column("unit_snapshot", sa.String(50), nullable=True),
        sa.Column("ref_range_snapshot", sa.String(255), nullable=True),
        sa.Column("collection_method_snapshot", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("package_id", "exam_item_id", name="uq_package_items_pkg_item"),
    )

    # ------------------------------------------------------------------
    # 4. Add package_id to exams
    # ------------------------------------------------------------------
    op.add_column("exams", sa.Column("package_id", sa.Integer,
                                     sa.ForeignKey("packages.id"), nullable=True))

    # ------------------------------------------------------------------
    # 5. Extend catalog_items with agricultural fields
    # ------------------------------------------------------------------
    op.add_column("catalog_items", sa.Column("grade", sa.String(50), nullable=True))
    op.add_column("catalog_items", sa.Column("specifications", sa.Text, nullable=True))
    op.add_column("catalog_items", sa.Column("origin", sa.String(255), nullable=True))
    op.add_column("catalog_items", sa.Column("harvest_batch", sa.String(100), nullable=True))
    op.add_column("catalog_items", sa.Column("harvest_date", sa.DateTime(timezone=True), nullable=True))
    op.add_column("catalog_items", sa.Column("packaging_info", sa.String(500), nullable=True))
    op.add_column("catalog_items", sa.Column("shelf_life_days", sa.Integer, nullable=True))
    op.create_check_constraint("ck_catalog_items_stock_non_negative", "catalog_items", "stock_quantity >= 0")
    op.create_check_constraint("ck_catalog_items_price_non_negative", "catalog_items", "price >= 0")
    op.create_check_constraint(
        "ck_catalog_items_shelf_life_positive", "catalog_items",
        "shelf_life_days IS NULL OR shelf_life_days > 0",
    )

    # ------------------------------------------------------------------
    # 6. Catalog attachments
    # ------------------------------------------------------------------
    op.create_table(
        "catalog_attachments",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("catalog_item_id", sa.Integer,
                  sa.ForeignKey("catalog_items.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("sha256_fingerprint", sa.String(64), nullable=False),
        sa.Column("uploaded_by", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("file_size <= 5242880", name="ck_catalog_attachments_size_limit"),
        sa.CheckConstraint("file_size > 0", name="ck_catalog_attachments_size_positive"),
    )

    # ------------------------------------------------------------------
    # 7. Orders + order items
    # ------------------------------------------------------------------
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("order_number", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("customer_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "order_type",
            sa.Enum("exam", "product", name="ordertype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "confirmed", "in_progress", "completed", "cancelled", name="orderstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("is_completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("total_amount >= 0", name="ck_orders_total_non_negative"),
    )

    op.create_table(
        "order_items",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("order_id", sa.Integer,
                  sa.ForeignKey("orders.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("item_id", sa.Integer, nullable=False),
        sa.Column("item_name_snapshot", sa.String(255), nullable=False),
        sa.Column("item_sku_snapshot", sa.String(100), nullable=True),
        sa.Column("unit_price_snapshot", sa.Numeric(10, 2), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False, server_default="1"),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("item_data_snapshot", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.CheckConstraint("unit_price_snapshot >= 0", name="ck_order_items_price_non_negative"),
        sa.CheckConstraint("subtotal >= 0", name="ck_order_items_subtotal_non_negative"),
    )

    # ------------------------------------------------------------------
    # 8. Rebuild reviews: add order_id, images, tags, follow-up, anti-spam
    #    Drop the old enum and recreate with "catalog_item" added.
    # ------------------------------------------------------------------
    # Add new columns to existing reviews table
    op.add_column("reviews", sa.Column("order_id", sa.Integer,
                                        sa.ForeignKey("orders.id"), nullable=True))  # nullable during migration
    op.add_column("reviews", sa.Column("tags", sa.Text, nullable=True))
    op.add_column("reviews", sa.Column("is_followup", sa.Boolean, nullable=False, server_default="false"))
    op.add_column("reviews", sa.Column("parent_review_id", sa.Integer,
                                        sa.ForeignKey("reviews.id"), nullable=True))
    op.add_column("reviews", sa.Column("followup_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reviews", sa.Column("submitted_at", sa.DateTime(timezone=True),
                                        nullable=False, server_default=sa.func.now()))

    # Extend the enum type (PostgreSQL supports ALTER TYPE … ADD VALUE)
    op.execute("ALTER TYPE reviewsubjecttype ADD VALUE IF NOT EXISTS 'catalog_item'")

    # Add rating constraint
    op.create_check_constraint("ck_reviews_rating_range", "reviews", "rating >= 1 AND rating <= 5")

    # Review images
    op.create_table(
        "review_images",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("review_id", sa.Integer,
                  sa.ForeignKey("reviews.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("sha256_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("file_size > 0", name="ck_review_images_size_positive"),
    )

    # ------------------------------------------------------------------
    # 9. Notifications
    # ------------------------------------------------------------------
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("recipient_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column(
            "notification_type",
            sa.Enum("info", "warning", "error", "success", "system", name="notificationtype"),
            nullable=False,
            server_default="info",
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("related_entity_type", sa.String(50), nullable=True),
        sa.Column("related_entity_id", sa.Integer, nullable=True),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "delivered", "retrying", "failed", name="notificationstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("delivery_attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("delivery_attempts <= 4", name="ck_notifications_max_attempts"),
        sa.CheckConstraint("delivery_attempts >= 0", name="ck_notifications_attempts_non_negative"),
    )

    # ------------------------------------------------------------------
    # 10. Rebuild cms_pages: add status, multi-store, SEO, sitemap, revisions
    # ------------------------------------------------------------------
    # Create new enum types for CMS
    op.execute(
        "CREATE TYPE cmspagestatustype AS ENUM ('draft', 'review', 'published', 'archived')"
    )
    op.execute(
        "CREATE TYPE sitemapchangefreqtype AS ENUM "
        "('always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never')"
    )

    # Add new columns to cms_pages
    op.add_column("cms_pages", sa.Column(
        "status",
        sa.Enum("draft", "review", "published", "archived", name="cmspagestatustype"),
        nullable=False, server_default="draft",
    ))
    op.add_column("cms_pages", sa.Column("store_id", sa.String(100), nullable=False, server_default="default"))
    op.add_column("cms_pages", sa.Column("locale", sa.String(10), nullable=False, server_default="en"))
    op.add_column("cms_pages", sa.Column("seo_title", sa.String(255), nullable=True))
    op.add_column("cms_pages", sa.Column("seo_description", sa.String(500), nullable=True))
    op.add_column("cms_pages", sa.Column("seo_keywords", sa.Text, nullable=True))
    op.add_column("cms_pages", sa.Column("is_in_sitemap", sa.Boolean, nullable=False, server_default="true"))
    op.add_column("cms_pages", sa.Column("sitemap_priority", sa.Numeric(2, 1), nullable=False, server_default="0.5"))
    op.add_column("cms_pages", sa.Column(
        "sitemap_changefreq",
        sa.Enum("always", "hourly", "daily", "weekly", "monthly", "yearly", "never",
                name="sitemapchangefreqtype"),
        nullable=False, server_default="monthly",
    ))
    op.add_column("cms_pages", sa.Column("current_revision", sa.Integer, nullable=False, server_default="1"))
    op.add_column("cms_pages", sa.Column("published_by", sa.Integer,
                                          sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    op.add_column("cms_pages", sa.Column("reviewed_by", sa.Integer,
                                          sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True))
    op.add_column("cms_pages", sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("cms_pages", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))

    # Drop old unique constraint on slug alone; replace with (slug, store_id, locale)
    op.execute("ALTER TABLE cms_pages DROP CONSTRAINT IF EXISTS cms_pages_slug_key")
    op.create_unique_constraint("uq_cms_pages_slug_store_locale", "cms_pages",
                                 ["slug", "store_id", "locale"])
    op.create_check_constraint(
        "ck_cms_pages_sitemap_priority_range", "cms_pages",
        "sitemap_priority >= 0.0 AND sitemap_priority <= 1.0",
    )

    # CMS page revisions
    op.create_table(
        "cms_page_revisions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("page_id", sa.Integer,
                  sa.ForeignKey("cms_pages.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("revision_number", sa.Integer, nullable=False),
        sa.Column("title_snapshot", sa.String(500), nullable=False),
        sa.Column("content_snapshot", sa.Text, nullable=False),
        sa.Column("status_snapshot", sa.String(20), nullable=False),
        sa.Column("seo_title_snapshot", sa.String(255), nullable=True),
        sa.Column("seo_description_snapshot", sa.String(500), nullable=True),
        sa.Column("changed_by", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("page_id", "revision_number", name="uq_cms_revisions_page_rev"),
        sa.CheckConstraint(
            "revision_number >= 1 AND revision_number <= 30",
            name="ck_cms_revisions_number_range",
        ),
    )


def downgrade() -> None:
    # CMS revisions
    op.drop_table("cms_page_revisions")

    # Revert cms_pages
    op.drop_constraint("uq_cms_pages_slug_store_locale", "cms_pages", type_="unique")
    op.drop_constraint("ck_cms_pages_sitemap_priority_range", "cms_pages", type_="check")
    op.create_unique_constraint("cms_pages_slug_key", "cms_pages", ["slug"])
    for col in ["status", "store_id", "locale", "seo_title", "seo_description", "seo_keywords",
                "is_in_sitemap", "sitemap_priority", "sitemap_changefreq", "current_revision",
                "published_by", "reviewed_by", "published_at", "reviewed_at"]:
        op.drop_column("cms_pages", col)
    op.execute("DROP TYPE IF EXISTS cmspagestatustype")
    op.execute("DROP TYPE IF EXISTS sitemapchangefreqtype")

    # Notifications
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS notificationstatus")

    # Reviews
    op.drop_table("review_images")
    for col in ["order_id", "tags", "is_followup", "parent_review_id",
                "followup_deadline", "submitted_at"]:
        op.drop_column("reviews", col)
    op.drop_constraint("ck_reviews_rating_range", "reviews", type_="check")

    # Orders
    op.drop_table("order_items")
    op.drop_table("orders")
    op.execute("DROP TYPE IF EXISTS orderstatus")
    op.execute("DROP TYPE IF EXISTS ordertype")

    # Catalog
    op.drop_table("catalog_attachments")
    for col in ["grade", "specifications", "origin", "harvest_batch", "harvest_date",
                "packaging_info", "shelf_life_days"]:
        op.drop_column("catalog_items", col)

    # Packages / exam items
    op.drop_column("exams", "package_id")
    op.drop_table("package_items")
    op.drop_table("packages")
    op.drop_table("exam_items")
    op.execute("DROP TYPE IF EXISTS examitemsex")

    # Users
    for col in ["last_login", "session_token_hash", "session_expires_at",
                "failed_login_attempts", "locked_until", "updated_at"]:
        op.drop_column("users", col)
