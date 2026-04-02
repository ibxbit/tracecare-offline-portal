from datetime import datetime, date
from pydantic import BaseModel
from app.models.product import TraceEventType


class ProductCreate(BaseModel):
    name: str
    sku: str
    origin: str | None = None
    batch_number: str | None = None
    harvest_date: date | None = None
    processing_date: date | None = None
    expiry_date: date | None = None


class ProductUpdate(BaseModel):
    name: str | None = None
    origin: str | None = None
    batch_number: str | None = None
    harvest_date: date | None = None
    processing_date: date | None = None
    expiry_date: date | None = None


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    origin: str | None
    batch_number: str | None
    harvest_date: date | None
    processing_date: date | None
    expiry_date: date | None
    created_by: int
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceEventCreate(BaseModel):
    event_type: TraceEventType
    location: str | None = None
    timestamp: datetime
    notes: str | None = None


class TraceEventResponse(BaseModel):
    id: int
    product_id: int
    event_type: TraceEventType
    location: str | None
    timestamp: datetime
    operator_id: int
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
