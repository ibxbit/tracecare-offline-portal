import enum
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Enum as SAEnum,
    Numeric, Integer, Boolean, CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class OrderType(str, enum.Enum):
    exam = "exam"
    product = "product"


class Order(Base):
    """
    Tracks a customer order (exam package or agricultural product purchase).
    Item details are preserved as snapshots in OrderItem so the record
    remains accurate even after catalog/package edits.
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    order_type: Mapped[OrderType] = mapped_column(SAEnum(OrderType), nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        SAEnum(OrderStatus), nullable=False, default=OrderStatus.pending
    )
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
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

    customer = relationship("User", foreign_keys=[customer_id])
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="order")

    __table_args__ = (
        CheckConstraint("total_amount >= 0", name="ck_orders_total_non_negative"),
    )


class OrderItem(Base):
    """
    A single line in an order.
    All pricing and item metadata is snapshotted at order creation time
    to ensure historical traceability (immutable once created).
    """
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # What was ordered — type + ID point to the live record; snapshot fields preserve history
    item_type: Mapped[str] = mapped_column(String(50), nullable=False)       # "exam_package" | "catalog_item"
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)             # live FK (soft ref, no DB FK)
    item_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    item_sku_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unit_price_snapshot: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Full JSON snapshot for complete historical detail
    item_data_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON stored as text

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    order = relationship("Order", back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        CheckConstraint("unit_price_snapshot >= 0", name="ck_order_items_price_non_negative"),
        CheckConstraint("subtotal >= 0", name="ck_order_items_subtotal_non_negative"),
    )
