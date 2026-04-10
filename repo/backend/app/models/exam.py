import enum
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, DateTime, Date, ForeignKey, Enum as SAEnum,
    Integer, Numeric, Boolean, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ExamStatus(str, enum.Enum):
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class ExamItemSex(str, enum.Enum):
    male = "male"
    female = "female"
    all = "all"


# ---------------------------------------------------------------------------
# ExamItem — master dictionary of testable items
# ---------------------------------------------------------------------------

class ExamItem(Base):
    """
    Dictionary of every exam / lab item the clinic can order.
    Includes reference ranges, units, sex/age applicability,
    contraindications, and collection methods.
    """
    __tablename__ = "exam_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Units & reference range
    unit: Mapped[str | None] = mapped_column(String(50), nullable=True)          # e.g. "mg/dL"
    ref_range_min: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    ref_range_max: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    ref_range_text: Mapped[str | None] = mapped_column(String(255), nullable=True)  # for non-numeric / composite

    # Applicability rules
    applicable_sex: Mapped[ExamItemSex] = mapped_column(
        SAEnum(ExamItemSex), nullable=False, default=ExamItemSex.all
    )
    min_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_age_years: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Clinical metadata
    contraindications: Mapped[str | None] = mapped_column(Text, nullable=True)    # JSON array stored as text
    collection_method: Mapped[str | None] = mapped_column(String(255), nullable=True)  # venipuncture, fingerstick…
    preparation_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)  # fasting, etc.

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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
    package_items = relationship("PackageItem", back_populates="exam_item")

    __table_args__ = (
        CheckConstraint(
            "(ref_range_min IS NULL OR ref_range_max IS NULL) OR ref_range_min <= ref_range_max",
            name="ck_exam_items_ref_range_order",
        ),
        CheckConstraint(
            "(min_age_years IS NULL OR max_age_years IS NULL) OR min_age_years <= max_age_years",
            name="ck_exam_items_age_range_order",
        ),
    )


# ---------------------------------------------------------------------------
# Package — versioned bundles of ExamItems
# ---------------------------------------------------------------------------

class Package(Base):
    """
    A named bundle of exam items (e.g. 'Full Blood Panel').
    Each time the composition changes, a new version row is inserted
    so older orders preserve their historical snapshot.

    Versioning rules:
      - (name, version) is unique; version increments on every structural change.
      - Only one version per name should have is_active=True at any time
        (enforced at application layer by activate/deactivate endpoints).
      - validity_window_days: how many days after the exam date the results
        are clinically valid; NULL means no expiry.
    """
    __tablename__ = "packages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Pricing (USD)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False, default=0)

    # Validity window — results valid for N days after the exam
    validity_window_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    creator = relationship("User", foreign_keys=[created_by])
    items = relationship("PackageItem", back_populates="package", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_packages_name_version"),
        CheckConstraint("price >= 0", name="ck_packages_price_non_negative"),
        CheckConstraint(
            "validity_window_days IS NULL OR validity_window_days > 0",
            name="ck_packages_validity_positive",
        ),
    )


class PackageItem(Base):
    """
    A single exam-item slot within a Package.
    Stores a denormalised snapshot of the item's key attributes
    so historical packages remain accurate even if ExamItem is edited.
    is_required=False marks the item as optional (patient/staff can skip).
    """
    __tablename__ = "package_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id"), nullable=False)
    exam_item_id: Mapped[int] = mapped_column(ForeignKey("exam_items.id"), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- snapshot fields (denormalised for historical preservation) ---
    item_code_snapshot: Mapped[str] = mapped_column(String(50), nullable=False)
    item_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_snapshot: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ref_range_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    collection_method_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    package = relationship("Package", back_populates="items")
    exam_item = relationship("ExamItem", back_populates="package_items")

    __table_args__ = (
        UniqueConstraint("package_id", "exam_item_id", name="uq_package_items_pkg_item"),
    )


# ---------------------------------------------------------------------------
# Exam — a clinic encounter linked to a patient
# ---------------------------------------------------------------------------

class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    staff_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    package_id: Mapped[int | None] = mapped_column(ForeignKey("packages.id"), nullable=True)
    exam_type: Mapped[str] = mapped_column(String(200), nullable=False)
    findings_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ExamStatus] = mapped_column(
        SAEnum(ExamStatus), nullable=False, default=ExamStatus.scheduled
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient = relationship("User", foreign_keys=[patient_id])
    staff = relationship("User", foreign_keys=[staff_id])
    package = relationship("Package", foreign_keys=[package_id])
