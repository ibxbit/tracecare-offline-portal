"""
Exam Items Dictionary
=====================
Manages the master list of testable exam / lab items.

RBAC
----
  Write (create, update, deactivate): admin, clinic_staff
  Read: all authenticated users
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models.exam import ExamItem, ExamItemSex
from app.models.user import User
from app.core.dependencies import get_current_user, require_role
from app.schemas.exam import ExamItemCreate, ExamItemUpdate, ExamItemResponse

router = APIRouter(prefix="/exam-items", tags=["exam-items"])

_WRITERS = ("admin", "clinic_staff")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(db: Session, item_id: int) -> ExamItem:
    item = db.execute(select(ExamItem).where(ExamItem.id == item_id)).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam item not found")
    return item


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=ExamItemResponse, status_code=status.HTTP_201_CREATED)
def create_exam_item(
    payload: ExamItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """Create a new exam item in the master dictionary."""
    # Ensure code uniqueness
    existing = db.execute(
        select(ExamItem).where(ExamItem.code == payload.code.upper())
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Exam item with code '{payload.code}' already exists (id={existing.id})",
        )

    item = ExamItem(
        code=payload.code.upper().strip(),
        name=payload.name.strip(),
        description=payload.description,
        unit=payload.unit,
        ref_range_min=payload.ref_range_min,
        ref_range_max=payload.ref_range_max,
        ref_range_text=payload.ref_range_text,
        applicable_sex=payload.applicable_sex,
        min_age_years=payload.min_age_years,
        max_age_years=payload.max_age_years,
        contraindications=payload.contraindications,
        collection_method=payload.collection_method,
        preparation_instructions=payload.preparation_instructions,
        is_active=True,
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("", response_model=list[ExamItemResponse])
def list_exam_items(
    active_only: bool = Query(default=True, description="Return only active items"),
    sex: ExamItemSex | None = Query(default=None, description="Filter by applicable sex"),
    search: str | None = Query(default=None, max_length=100, description="Search code or name"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List exam items with optional filters."""
    q = select(ExamItem)
    if active_only:
        q = q.where(ExamItem.is_active == True)  # noqa: E712
    if sex is not None:
        q = q.where(
            (ExamItem.applicable_sex == sex) | (ExamItem.applicable_sex == ExamItemSex.all)
        )
    if search:
        term = f"%{search.lower()}%"
        q = q.where(
            ExamItem.code.ilike(term) | ExamItem.name.ilike(term)
        )
    q = q.order_by(ExamItem.code).offset(skip).limit(limit)
    return db.execute(q).scalars().all()


@router.get("/{item_id}", response_model=ExamItemResponse)
def get_exam_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Retrieve a single exam item by ID."""
    return _get_or_404(db, item_id)


@router.put("/{item_id}", response_model=ExamItemResponse)
def update_exam_item(
    item_id: int,
    payload: ExamItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """
    Update an exam item in-place.

    Note: this updates the master dictionary only. Existing PackageItem
    snapshots are NOT affected — they were frozen at package composition time.
    Future package versions will pick up the new values when re-snapshotted.
    """
    item = _get_or_404(db, item_id)

    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )

    # Validate ref range consistency after partial update
    new_min = update_data.get("ref_range_min", item.ref_range_min)
    new_max = update_data.get("ref_range_max", item.ref_range_max)
    if new_min is not None and new_max is not None and new_min > new_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ref_range_min must be <= ref_range_max",
        )

    new_min_age = update_data.get("min_age_years", item.min_age_years)
    new_max_age = update_data.get("max_age_years", item.max_age_years)
    if new_min_age is not None and new_max_age is not None and new_min_age > new_max_age:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_age_years must be <= max_age_years",
        )

    for field, value in update_data.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_exam_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Soft-delete an exam item by setting is_active=False.
    Hard deletion is intentionally not supported to preserve traceability
    in existing package snapshots and completed exam records.
    """
    item = _get_or_404(db, item_id)
    if not item.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam item is already inactive",
        )
    item.is_active = False
    db.commit()


@router.patch("/{item_id}/reactivate", response_model=ExamItemResponse)
def reactivate_exam_item(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """Re-enable a previously deactivated exam item."""
    item = _get_or_404(db, item_id)
    if item.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam item is already active",
        )
    item.is_active = True
    db.commit()
    db.refresh(item)
    return item
