from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database import get_db
from app.models.product import Product, TraceEvent
from app.models.user import User
from app.core.dependencies import get_current_user, require_role
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductResponse,
    TraceEventCreate, TraceEventResponse,
)

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "catalog_manager")),
):
    existing = db.execute(
        select(Product).where(Product.sku == payload.sku)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU already exists",
        )
    product = Product(
        name=payload.name,
        sku=payload.sku,
        origin=payload.origin,
        batch_number=payload.batch_number,
        harvest_date=payload.harvest_date,
        processing_date=payload.processing_date,
        expiry_date=payload.expiry_date,
        created_by=current_user.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    products = db.execute(select(Product).offset(skip).limit(limit)).scalars().all()
    return products


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "catalog_manager")),
):
    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "catalog_manager")),
):
    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    db.delete(product)
    db.commit()


@router.post(
    "/{product_id}/trace-events",
    response_model=TraceEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_trace_event(
    product_id: int,
    payload: TraceEventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "catalog_manager")),
):
    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    event = TraceEvent(
        product_id=product_id,
        event_type=payload.event_type,
        location=payload.location,
        timestamp=payload.timestamp,
        operator_id=current_user.id,
        notes=payload.notes,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/{product_id}/trace-events", response_model=list[TraceEventResponse])
def get_trace_events(
    product_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    product = db.execute(
        select(Product).where(Product.id == product_id)
    ).scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    events = db.execute(
        select(TraceEvent)
        .where(TraceEvent.product_id == product_id)
        .order_by(TraceEvent.timestamp)
    ).scalars().all()
    return events
