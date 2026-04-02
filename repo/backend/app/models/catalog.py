import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Numeric, Integer, Boolean,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# Allowed MIME types for catalog attachments
ALLOWED_MIME_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain", "text/csv",
}

# 5 MB in bytes
MAX_ATTACHMENT_SIZE_BYTES = 5 * 1024 * 1024  # 5242880


class CatalogItem(Base):
    """
    Agricultural product catalog entry.
    Includes agronomic metadata: grade, specs, origin, batch, packaging,
    and shelf life. Attachments are stored in CatalogAttachment.
    """
    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)

    # Pricing & stock
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    stock_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Agricultural-specific fields
    grade: Mapped[str | None] = mapped_column(String(50), nullable=True)           # A, B, Premium…
    specifications: Mapped[str | None] = mapped_column(Text, nullable=True)         # JSON key-value specs
    origin: Mapped[str | None] = mapped_column(String(255), nullable=True)          # country / region
    harvest_batch: Mapped[str | None] = mapped_column(String(100), nullable=True)   # batch / lot number
    harvest_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    packaging_info: Mapped[str | None] = mapped_column(String(500), nullable=True)  # "10 kg sack", "crate of 24"
    shelf_life_days: Mapped[int | None] = mapped_column(Integer, nullable=True)      # days from harvest

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by])
    attachments = relationship(
        "CatalogAttachment",
        back_populates="catalog_item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("stock_quantity >= 0", name="ck_catalog_items_stock_non_negative"),
        CheckConstraint("price >= 0", name="ck_catalog_items_price_non_negative"),
        CheckConstraint(
            "shelf_life_days IS NULL OR shelf_life_days > 0",
            name="ck_catalog_items_shelf_life_positive",
        ),
    )


class CatalogAttachment(Base):
    """
    File attachment for a catalog entry.
    Enforces MIME type and 5 MB size limit at the application layer
    (see ALLOWED_MIME_TYPES and MAX_ATTACHMENT_SIZE_BYTES constants).
    sha256_fingerprint provides a cryptographic integrity check.
    """
    __tablename__ = "catalog_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_items.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # File metadata
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(500), nullable=False)     # UUID-based on disk
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)               # bytes

    # Cryptographic fingerprint (SHA-256 hex digest)
    sha256_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)

    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    catalog_item = relationship("CatalogItem", back_populates="attachments")
    uploader = relationship("User", foreign_keys=[uploaded_by])

    __table_args__ = (
        CheckConstraint(
            f"file_size <= {MAX_ATTACHMENT_SIZE_BYTES}",
            name="ck_catalog_attachments_size_limit",
        ),
        CheckConstraint("file_size > 0", name="ck_catalog_attachments_size_positive"),
    )
