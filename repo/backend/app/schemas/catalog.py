from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Sorting helpers
# ---------------------------------------------------------------------------

class CatalogSortField(str, Enum):
    name = "name"
    price = "price"
    stock_quantity = "stock_quantity"
    shelf_life_days = "shelf_life_days"
    created_at = "created_at"
    updated_at = "updated_at"
    harvest_date = "harvest_date"


class SortDir(str, Enum):
    asc = "asc"
    desc = "desc"


# ---------------------------------------------------------------------------
# CatalogItem schemas
# ---------------------------------------------------------------------------

class CatalogItemCreate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)]
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)

    # Pricing & stock
    price: Annotated[Decimal, Field(ge=0, decimal_places=2)] = Decimal("0.00")
    stock_quantity: Annotated[int, Field(ge=0)] = 0

    # Agricultural attributes
    grade: str | None = Field(default=None, max_length=50,
                               description="Quality grade: A, B, C, Premium, Organic, …")
    specifications: str | None = Field(
        default=None,
        description="JSON object of arbitrary key-value agronomic specs (moisture %, brix, …)"
    )
    origin: str | None = Field(default=None, max_length=255,
                                description="Country or region of origin")
    harvest_batch: str | None = Field(default=None, max_length=100,
                                       description="Batch / lot number from harvest")
    harvest_date: datetime | None = None
    packaging_info: str | None = Field(default=None, max_length=500,
                                        description="e.g. '10 kg sack', 'crate of 24 units'")
    shelf_life_days: Annotated[int, Field(gt=0)] | None = Field(
        default=None, description="Days of shelf life from harvest date"
    )

    # Tagging and priority
    tags: str | None = Field(
        default=None, max_length=500,
        description="Comma-separated keyword tags, e.g. 'organic,premium,export'",
    )
    priority: Annotated[int, Field(ge=1, le=5)] | None = Field(
        default=None, description="Priority 1 (low) to 5 (critical)"
    )

    @field_validator("specifications")
    @classmethod
    def validate_specifications_json(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import json
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("specifications must be a JSON object (dict)")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"specifications is not valid JSON: {exc}") from exc
        return v


class CatalogItemUpdate(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=255)] | None = None
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    price: Annotated[Decimal, Field(ge=0, decimal_places=2)] | None = None
    stock_quantity: Annotated[int, Field(ge=0)] | None = None
    grade: str | None = Field(default=None, max_length=50)
    specifications: str | None = None
    origin: str | None = Field(default=None, max_length=255)
    harvest_batch: str | None = Field(default=None, max_length=100)
    harvest_date: datetime | None = None
    packaging_info: str | None = Field(default=None, max_length=500)
    shelf_life_days: Annotated[int, Field(gt=0)] | None = None
    is_active: bool | None = None
    tags: str | None = Field(default=None, max_length=500)
    priority: Annotated[int, Field(ge=1, le=5)] | None = None

    @field_validator("specifications")
    @classmethod
    def validate_specifications_json(cls, v: str | None) -> str | None:
        if v is None:
            return v
        import json
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, dict):
                raise ValueError("specifications must be a JSON object (dict)")
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"specifications is not valid JSON: {exc}") from exc
        return v


class CatalogAttachmentResponse(BaseModel):
    id: int
    catalog_item_id: int
    original_filename: str
    stored_filename: str
    mime_type: str
    file_size: int
    sha256_fingerprint: str
    uploaded_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class CatalogItemResponse(BaseModel):
    id: int
    name: str
    description: str | None
    category: str | None

    price: Decimal
    stock_quantity: int

    grade: str | None
    specifications: str | None
    origin: str | None
    harvest_batch: str | None
    harvest_date: datetime | None
    packaging_info: str | None
    shelf_life_days: int | None

    is_active: bool
    tags: str | None
    priority: int | None
    created_by: int
    created_at: datetime
    updated_at: datetime

    attachments: list[CatalogAttachmentResponse] = []

    model_config = {"from_attributes": True}


class CatalogItemBrief(BaseModel):
    """Lightweight response for list endpoints (no attachments)."""
    id: int
    name: str
    category: str | None
    price: Decimal
    stock_quantity: int
    grade: str | None
    origin: str | None
    harvest_batch: str | None
    shelf_life_days: int | None
    is_active: bool
    tags: str | None
    priority: int | None
    created_at: datetime
    updated_at: datetime
    attachment_count: int = 0

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Stock adjustment
# ---------------------------------------------------------------------------

class StockAdjust(BaseModel):
    adjustment: int = Field(
        description="Positive to add stock, negative to remove. Result must be >= 0."
    )
    reason: str | None = Field(default=None, max_length=500)


class StockSet(BaseModel):
    """Directly set stock to an absolute value (admin only)."""
    quantity: Annotated[int, Field(ge=0)]
    reason: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Attachment integrity verification response
# ---------------------------------------------------------------------------

class AttachmentVerifyResponse(BaseModel):
    attachment_id: int
    original_filename: str
    stored_fingerprint: str
    computed_fingerprint: str
    integrity_ok: bool
    message: str
