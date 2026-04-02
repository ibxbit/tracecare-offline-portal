from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from pydantic import BaseModel, Field, field_validator, model_validator
from app.models.exam import ExamStatus, ExamItemSex


# ---------------------------------------------------------------------------
# ExamItem schemas
# ---------------------------------------------------------------------------

class ExamItemCreate(BaseModel):
    code: Annotated[str, Field(min_length=1, max_length=50)]
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    unit: str | None = Field(default=None, max_length=50)
    ref_range_min: Decimal | None = None
    ref_range_max: Decimal | None = None
    ref_range_text: str | None = Field(default=None, max_length=255)
    applicable_sex: ExamItemSex = ExamItemSex.all
    min_age_years: int | None = Field(default=None, ge=0, le=150)
    max_age_years: int | None = Field(default=None, ge=0, le=150)
    contraindications: str | None = None       # JSON array as text
    collection_method: str | None = Field(default=None, max_length=255)
    preparation_instructions: str | None = None

    @model_validator(mode="after")
    def check_ref_range_order(self) -> ExamItemCreate:
        lo, hi = self.ref_range_min, self.ref_range_max
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("ref_range_min must be <= ref_range_max")
        return self

    @model_validator(mode="after")
    def check_age_range_order(self) -> ExamItemCreate:
        lo, hi = self.min_age_years, self.max_age_years
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("min_age_years must be <= max_age_years")
        return self


class ExamItemUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    description: str | None = None
    unit: str | None = Field(default=None, max_length=50)
    ref_range_min: Decimal | None = None
    ref_range_max: Decimal | None = None
    ref_range_text: str | None = Field(default=None, max_length=255)
    applicable_sex: ExamItemSex | None = None
    min_age_years: int | None = Field(default=None, ge=0, le=150)
    max_age_years: int | None = Field(default=None, ge=0, le=150)
    contraindications: str | None = None
    collection_method: str | None = Field(default=None, max_length=255)
    preparation_instructions: str | None = None
    is_active: bool | None = None


class ExamItemResponse(BaseModel):
    id: int
    code: str
    name: str
    description: str | None
    unit: str | None
    ref_range_min: Decimal | None
    ref_range_max: Decimal | None
    ref_range_text: str | None
    applicable_sex: ExamItemSex
    min_age_years: int | None
    max_age_years: int | None
    contraindications: str | None
    collection_method: str | None
    preparation_instructions: str | None
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Package schemas
# ---------------------------------------------------------------------------

class PackageItemIn(BaseModel):
    """Describes one exam item slot when creating or editing a package."""
    exam_item_id: int
    is_required: bool = True


class PackageCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    price: Annotated[Decimal, Field(ge=0, decimal_places=2)]
    validity_window_days: Annotated[int, Field(gt=0)] | None = None
    items: Annotated[list[PackageItemIn], Field(min_length=1)]

    @field_validator("items")
    @classmethod
    def no_duplicate_items(cls, v: list[PackageItemIn]) -> list[PackageItemIn]:
        ids = [i.exam_item_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate exam_item_id entries in items list")
        return v


class PackageNewVersionRequest(BaseModel):
    """
    Payload for bumping a package to a new version.
    Only provided fields are changed; the rest carry over from the previous version.
    At least one field must differ from the current version (validated in the router).
    """
    description: str | None = None
    price: Annotated[Decimal, Field(ge=0, decimal_places=2)] | None = None
    validity_window_days: Annotated[int, Field(gt=0)] | None = None
    items: list[PackageItemIn] | None = None

    @field_validator("items")
    @classmethod
    def no_duplicate_items(cls, v: list[PackageItemIn] | None) -> list[PackageItemIn] | None:
        if v is None:
            return v
        ids = [i.exam_item_id for i in v]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate exam_item_id entries in items list")
        return v


class PackageItemResponse(BaseModel):
    id: int
    exam_item_id: int
    is_required: bool
    item_code_snapshot: str
    item_name_snapshot: str
    unit_snapshot: str | None
    ref_range_snapshot: str | None
    collection_method_snapshot: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PackageResponse(BaseModel):
    id: int
    name: str
    description: str | None
    version: int
    price: Decimal
    validity_window_days: int | None
    is_active: bool
    created_by: int
    created_at: datetime
    items: list[PackageItemResponse]

    model_config = {"from_attributes": True}


class PackageBrief(BaseModel):
    """Lightweight listing response (no items list)."""
    id: int
    name: str
    version: int
    price: Decimal
    validity_window_days: int | None
    is_active: bool
    created_at: datetime
    item_count: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Diff response
# ---------------------------------------------------------------------------

class DiffItem(BaseModel):
    exam_item_id: int
    code: str
    name: str


class ChangedItem(BaseModel):
    exam_item_id: int
    code: str
    name: str
    changes: dict[str, dict]  # field -> {"from": old, "to": new}


class MetadataChange(BaseModel):
    field: str
    from_value: object
    to_value: object


class PackageDiffResponse(BaseModel):
    from_version: int
    to_version: int
    metadata_changes: list[MetadataChange]
    items_added: list[DiffItem]
    items_removed: list[DiffItem]
    items_changed: list[ChangedItem]   # same item, is_required flipped


# ---------------------------------------------------------------------------
# Exam schemas (updated to include package_id)
# ---------------------------------------------------------------------------

class ExamCreate(BaseModel):
    patient_id: int
    package_id: int | None = None
    exam_type: Annotated[str, Field(min_length=1, max_length=200)]
    scheduled_at: datetime
    notes: str | None = None


class ExamUpdate(BaseModel):
    findings: str | None = None
    status: ExamStatus | None = None
    notes: str | None = None
    completed_at: datetime | None = None


class ExamResponse(BaseModel):
    id: int
    patient_id: int
    staff_id: int
    package_id: int | None
    exam_type: str
    findings: str | None = None
    status: ExamStatus
    notes: str | None
    scheduled_at: datetime
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
