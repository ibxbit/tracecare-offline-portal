"""
Agricultural Catalog Module
============================
Manages catalog entries for agricultural products including grade, origin,
harvest batch, packaging specs, shelf life, and file attachments.

File attachments are stored on the local filesystem (offline-safe):
  - MIME type validated against an allow-list
  - Magic bytes sniffed to catch spoofed extensions
  - 5 MB size limit enforced before disk write
  - SHA-256 fingerprint computed and stored for offline integrity checks
  - Files served directly by FastAPI (no cloud/CDN)

RBAC
----
  Write (create, update, delete, upload): admin, catalog_manager
  Stock set (absolute):                   admin only
  Read / download:                        all authenticated users
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import (
    APIRouter, Depends, File, HTTPException, Query, Request,
    UploadFile, status,
)
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.core.dependencies import get_current_user, require_role
from app.core.file_utils import ValidationError, validate_upload, verify_file_integrity
from app.database import get_db
from app.models.catalog import (
    CatalogAttachment,
    CatalogItem,
    ALLOWED_MIME_TYPES,
    MAX_ATTACHMENT_SIZE_BYTES,
)
from app.models.user import User
from app.schemas.catalog import (
    AttachmentVerifyResponse,
    CatalogAttachmentResponse,
    CatalogItemBrief,
    CatalogItemCreate,
    CatalogItemResponse,
    CatalogItemUpdate,
    CatalogSortField,
    SortDir,
    StockAdjust,
    StockSet,
)

router = APIRouter(prefix="/catalog", tags=["catalog"])

_WRITERS = ("admin", "catalog_manager")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_item_or_404(db: Session, item_id: int, *, with_attachments: bool = False) -> CatalogItem:
    q = select(CatalogItem).where(CatalogItem.id == item_id)
    if with_attachments:
        q = q.options(selectinload(CatalogItem.attachments))
    item = db.execute(q).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")
    return item


def _get_attachment_or_404(db: Session, item_id: int, att_id: int) -> CatalogAttachment:
    att = db.execute(
        select(CatalogAttachment).where(
            CatalogAttachment.id == att_id,
            CatalogAttachment.catalog_item_id == item_id,
        )
    ).scalar_one_or_none()
    if not att:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Attachment {att_id} not found on catalog item {item_id}",
        )
    return att


def _item_dir(item_id: int) -> Path:
    """Return (and create) the per-item upload directory."""
    d = settings.attachments_path / str(item_id)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _to_brief(item: CatalogItem, attachment_count: int) -> CatalogItemBrief:
    return CatalogItemBrief(
        id=item.id,
        name=item.name,
        category=item.category,
        price=item.price,
        stock_quantity=item.stock_quantity,
        grade=item.grade,
        origin=item.origin,
        harvest_batch=item.harvest_batch,
        shelf_life_days=item.shelf_life_days,
        is_active=item.is_active,
        tags=item.tags,
        priority=item.priority,
        created_at=item.created_at,
        updated_at=item.updated_at,
        attachment_count=attachment_count,
    )


# ---------------------------------------------------------------------------
# CRUD endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=CatalogItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: CatalogItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """Create a new agricultural catalog entry."""
    item = CatalogItem(
        name=payload.name.strip(),
        description=payload.description,
        category=payload.category,
        price=payload.price,
        stock_quantity=payload.stock_quantity,
        grade=payload.grade,
        specifications=payload.specifications,
        origin=payload.origin,
        harvest_batch=payload.harvest_batch,
        harvest_date=payload.harvest_date,
        packaging_info=payload.packaging_info,
        shelf_life_days=payload.shelf_life_days,
        tags=payload.tags,
        priority=payload.priority,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    # Reload with attachments relationship
    return _get_item_or_404(db, item.id, with_attachments=True)


@router.get("", response_model=list[CatalogItemBrief])
def list_items(
    # --- text search ---
    search: str | None = Query(default=None, max_length=200,
                                description="Full-text search across name, description, category, origin"),
    name: str | None = Query(default=None, max_length=255),
    category: str | None = Query(default=None, max_length=100),
    grade: str | None = Query(default=None, max_length=50),
    origin: str | None = Query(default=None, max_length=255),
    harvest_batch: str | None = Query(default=None, max_length=100),

    # --- numeric range filters ---
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    stock_min: int | None = Query(default=None, ge=0),
    stock_max: int | None = Query(default=None, ge=0),
    shelf_life_min: int | None = Query(default=None, ge=1),
    shelf_life_max: int | None = Query(default=None, ge=1),

    # --- date range ---
    harvest_date_from: datetime | None = Query(default=None),
    harvest_date_to: datetime | None = Query(default=None),

    # --- tags and priority ---
    tags: str | None = Query(
        default=None, max_length=500,
        description="Comma-separated tags; returns items whose tags column contains ANY listed tag",
    ),
    priority_min: int | None = Query(default=None, ge=1, le=5,
                                      description="Minimum priority (1=low … 5=critical)"),
    priority_max: int | None = Query(default=None, ge=1, le=5,
                                      description="Maximum priority (1=low … 5=critical)"),

    # --- boolean flags ---
    active_only: bool = Query(default=True),
    in_stock: bool = Query(default=False, description="Only items with stock_quantity > 0"),

    # --- sorting ---
    sort_by: CatalogSortField = Query(default=CatalogSortField.name),
    sort_dir: SortDir = Query(default=SortDir.asc),

    # --- pagination ---
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),

    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    List catalog items with multi-criteria filtering.

    All filters are AND-combined.  `search` does a case-insensitive OR
    across name, description, category, and origin.
    """
    q = select(CatalogItem)

    # Boolean flags
    if active_only:
        q = q.where(CatalogItem.is_active == True)  # noqa: E712
    if in_stock:
        q = q.where(CatalogItem.stock_quantity > 0)

    # Text filters
    if search:
        term = f"%{search}%"
        q = q.where(
            or_(
                CatalogItem.name.ilike(term),
                CatalogItem.description.ilike(term),
                CatalogItem.category.ilike(term),
                CatalogItem.origin.ilike(term),
            )
        )
    if name:
        q = q.where(CatalogItem.name.ilike(f"%{name}%"))
    if category:
        q = q.where(CatalogItem.category.ilike(f"%{category}%"))
    if grade:
        q = q.where(CatalogItem.grade.ilike(f"%{grade}%"))
    if origin:
        q = q.where(CatalogItem.origin.ilike(f"%{origin}%"))
    if harvest_batch:
        q = q.where(CatalogItem.harvest_batch.ilike(f"%{harvest_batch}%"))

    # Numeric ranges
    if price_min is not None:
        q = q.where(CatalogItem.price >= price_min)
    if price_max is not None:
        q = q.where(CatalogItem.price <= price_max)
    if stock_min is not None:
        q = q.where(CatalogItem.stock_quantity >= stock_min)
    if stock_max is not None:
        q = q.where(CatalogItem.stock_quantity <= stock_max)
    if shelf_life_min is not None:
        q = q.where(CatalogItem.shelf_life_days >= shelf_life_min)
    if shelf_life_max is not None:
        q = q.where(CatalogItem.shelf_life_days <= shelf_life_max)

    # Date ranges
    if harvest_date_from is not None:
        q = q.where(CatalogItem.harvest_date >= harvest_date_from)
    if harvest_date_to is not None:
        q = q.where(CatalogItem.harvest_date <= harvest_date_to)

    # Tags — match any comma-separated tag (case-insensitive substring per tag)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        if tag_list:
            q = q.where(or_(*[CatalogItem.tags.ilike(f"%{t}%") for t in tag_list]))

    # Priority range
    if priority_min is not None:
        q = q.where(CatalogItem.priority >= priority_min)
    if priority_max is not None:
        q = q.where(CatalogItem.priority <= priority_max)

    # Validate range pairs
    if price_min is not None and price_max is not None and price_min > price_max:
        raise HTTPException(status_code=422, detail="price_min must be <= price_max")
    if stock_min is not None and stock_max is not None and stock_min > stock_max:
        raise HTTPException(status_code=422, detail="stock_min must be <= stock_max")
    if shelf_life_min is not None and shelf_life_max is not None and shelf_life_min > shelf_life_max:
        raise HTTPException(status_code=422, detail="shelf_life_min must be <= shelf_life_max")
    if priority_min is not None and priority_max is not None and priority_min > priority_max:
        raise HTTPException(status_code=422, detail="priority_min must be <= priority_max")

    # Sorting
    sort_col = getattr(CatalogItem, sort_by.value)
    q = q.order_by(sort_col.asc() if sort_dir == SortDir.asc else sort_col.desc())

    # Attachment counts in a single subquery to avoid N+1
    att_counts_rows = db.execute(
        select(
            CatalogAttachment.catalog_item_id,
            func.count(CatalogAttachment.id).label("cnt"),
        ).group_by(CatalogAttachment.catalog_item_id)
    ).all()
    att_counts: dict[int, int] = {row.catalog_item_id: row.cnt for row in att_counts_rows}

    items = db.execute(q.offset(skip).limit(limit)).scalars().all()
    return [_to_brief(it, att_counts.get(it.id, 0)) for it in items]


@router.get("/{item_id}", response_model=CatalogItemResponse)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Retrieve a single catalog item including its attachment list."""
    return _get_item_or_404(db, item_id, with_attachments=True)


@router.put("/{item_id}", response_model=CatalogItemResponse)
def update_item(
    item_id: int,
    payload: CatalogItemUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """Full or partial update of a catalog entry (all fields optional)."""
    item = _get_item_or_404(db, item_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=422, detail="No fields provided for update")

    for field, value in update_data.items():
        setattr(item, field, value)
    item.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(item)
    return _get_item_or_404(db, item_id, with_attachments=True)


@router.patch("/{item_id}/deactivate", response_model=CatalogItemResponse)
def deactivate_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Soft-delete: mark item as inactive.
    Preserves all data and attachments; item no longer appears in default listings.
    """
    item = _get_item_or_404(db, item_id)
    if not item.is_active:
        raise HTTPException(status_code=409, detail="Item is already inactive")
    item.is_active = False
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _get_item_or_404(db, item_id, with_attachments=True)


@router.patch("/{item_id}/reactivate", response_model=CatalogItemResponse)
def reactivate_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """Re-enable a previously deactivated catalog item."""
    item = _get_item_or_404(db, item_id)
    if item.is_active:
        raise HTTPException(status_code=409, detail="Item is already active")
    item.is_active = True
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _get_item_or_404(db, item_id, with_attachments=True)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Hard-delete a catalog item and all its attachments (admin only).
    Attachment files are removed from disk.
    """
    item = _get_item_or_404(db, item_id, with_attachments=True)

    # Remove all attachment files from disk first
    item_dir = settings.attachments_path / str(item_id)
    for att in item.attachments:
        file_path = item_dir / att.stored_filename
        if file_path.exists():
            file_path.unlink(missing_ok=True)
    if item_dir.exists():
        try:
            item_dir.rmdir()  # only removes if empty
        except OSError:
            pass  # non-empty dir (unexpected leftover files) — leave it

    db.delete(item)
    db.commit()


# ---------------------------------------------------------------------------
# Stock management
# ---------------------------------------------------------------------------

@router.put("/{item_id}/stock", response_model=CatalogItemResponse)
def adjust_stock(
    item_id: int,
    payload: StockAdjust,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Adjust stock by a relative delta (positive = restock, negative = consume).
    Rejects adjustments that would make stock negative.
    """
    item = _get_item_or_404(db, item_id)
    new_stock = item.stock_quantity + payload.adjustment
    if new_stock < 0:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Adjustment of {payload.adjustment} would result in negative stock "
                f"(current={item.stock_quantity})"
            ),
        )
    item.stock_quantity = new_stock
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _get_item_or_404(db, item_id, with_attachments=True)


@router.put("/{item_id}/stock/set", response_model=CatalogItemResponse)
def set_stock(
    item_id: int,
    payload: StockSet,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Directly set stock to an absolute value (admin only — use for inventory corrections)."""
    item = _get_item_or_404(db, item_id)
    item.stock_quantity = payload.quantity
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _get_item_or_404(db, item_id, with_attachments=True)


# ---------------------------------------------------------------------------
# Attachment endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/{item_id}/attachments",
    response_model=CatalogAttachmentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_attachment(
    item_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """
    Upload a file attachment to a catalog entry.

    Validation (fully offline):
      - MIME type must be in the allow-list
      - Magic bytes must match the declared Content-Type
      - File must be <= 5 MB
      - File must not be empty

    The SHA-256 fingerprint is computed from the raw bytes and stored
    alongside the file metadata for later integrity verification.
    """
    item = _get_item_or_404(db, item_id)

    # Read file into memory for validation (max 5 MB is safe)
    data = await file.read()
    declared_mime = file.content_type or "application/octet-stream"
    original_filename = file.filename or "upload"

    try:
        fingerprint = validate_upload(
            data=data,
            declared_mime=declared_mime,
            original_filename=original_filename,
            allowed_mimes=ALLOWED_MIME_TYPES,
            max_size_bytes=MAX_ATTACHMENT_SIZE_BYTES,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Determine file extension from original name for readability
    suffix = Path(original_filename).suffix.lower() or ""
    stored_name = f"{uuid.uuid4().hex}{suffix}"

    dest_dir = _item_dir(item_id)
    dest_path = dest_dir / stored_name

    # Write to disk
    dest_path.write_bytes(data)

    # Persist metadata
    att = CatalogAttachment(
        catalog_item_id=item_id,
        original_filename=original_filename,
        stored_filename=stored_name,
        mime_type=declared_mime.split(";")[0].strip().lower(),
        file_size=fingerprint.size_bytes,
        sha256_fingerprint=fingerprint.sha256,
        uploaded_by=current_user.id,
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


@router.get("/{item_id}/attachments", response_model=list[CatalogAttachmentResponse])
def list_attachments(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all attachments for a catalog item."""
    _get_item_or_404(db, item_id)   # confirm item exists
    atts = db.execute(
        select(CatalogAttachment)
        .where(CatalogAttachment.catalog_item_id == item_id)
        .order_by(CatalogAttachment.created_at)
    ).scalars().all()
    return atts


@router.get("/{item_id}/attachments/{att_id}/download")
def download_attachment(
    item_id: int,
    att_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Stream an attachment file directly from the local filesystem.
    Performs a SHA-256 integrity check before serving; aborts if the file
    has been tampered with since upload.
    """
    from app.core.audit import audit
    from app.core.file_utils import verify_file_integrity
    from app.models.audit import AuditEventType

    att = _get_attachment_or_404(db, item_id, att_id)
    file_path = settings.attachments_path / str(item_id) / att.stored_filename

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Attachment file not found on disk. "
                f"The record exists (id={att_id}) but the file is missing."
            ),
        )

    # Integrity check before serving
    raw = file_path.read_bytes()
    if not verify_file_integrity(raw, att.sha256_fingerprint):
        audit(db, AuditEventType.file_integrity_fail,
              user_id=current_user.id, username=current_user.username,
              ip=request.client.host if request.client else None,
              resource_type="catalog_attachment", resource_id=str(att_id),
              detail=f"SHA-256 mismatch for {att.original_filename}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="File integrity check failed. The attachment may have been modified.",
        )

    audit(db, AuditEventType.file_download,
          user_id=current_user.id, username=current_user.username,
          ip=request.client.host if request.client else None,
          resource_type="catalog_attachment", resource_id=str(att_id),
          detail=att.original_filename)

    return FileResponse(
        path=str(file_path),
        media_type=att.mime_type,
        filename=att.original_filename,
    )


@router.get(
    "/{item_id}/attachments/{att_id}/verify",
    response_model=AttachmentVerifyResponse,
)
def verify_attachment(
    item_id: int,
    att_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Offline integrity check: re-compute the file's SHA-256 and compare it
    to the fingerprint stored at upload time.

    Returns integrity_ok=True only if the file exists on disk and the
    fingerprints match byte-for-byte.  No network access required.
    """
    att = _get_attachment_or_404(db, item_id, att_id)
    file_path = settings.attachments_path / str(item_id) / att.stored_filename

    if not file_path.exists():
        return AttachmentVerifyResponse(
            attachment_id=att_id,
            original_filename=att.original_filename,
            stored_fingerprint=att.sha256_fingerprint,
            computed_fingerprint="",
            integrity_ok=False,
            message="File is missing from disk — it may have been deleted or moved.",
        )

    data = file_path.read_bytes()
    ok = verify_file_integrity(data, att.sha256_fingerprint)
    import hashlib
    computed = hashlib.sha256(data).hexdigest()

    return AttachmentVerifyResponse(
        attachment_id=att_id,
        original_filename=att.original_filename,
        stored_fingerprint=att.sha256_fingerprint,
        computed_fingerprint=computed,
        integrity_ok=ok,
        message="Integrity check passed." if ok else (
            "INTEGRITY FAILURE: file content has changed since upload. "
            "The file may have been tampered with or corrupted."
        ),
    )


@router.delete(
    "/{item_id}/attachments/{att_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_attachment(
    item_id: int,
    att_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Delete an attachment: removes the file from disk and the database record.
    If the file is missing from disk the database record is still removed.
    """
    att = _get_attachment_or_404(db, item_id, att_id)
    file_path = settings.attachments_path / str(item_id) / att.stored_filename

    if file_path.exists():
        file_path.unlink(missing_ok=True)

    db.delete(att)
    db.commit()


# ---------------------------------------------------------------------------
# Allowed MIME types — informational endpoint
# ---------------------------------------------------------------------------

@router.get("/meta/allowed-mime-types", response_model=list[str])
def get_allowed_mime_types(_: User = Depends(get_current_user)):
    """Return the list of accepted MIME types for catalog attachments."""
    return sorted(ALLOWED_MIME_TYPES)
