"""
Packages (versioned exam bundles)
==================================
Manages exam packages — versioned, USD-priced bundles of exam items.

Versioning contract
-------------------
- A package is identified by its *name*. Each structural change creates a new
  row with an incremented version number. Old rows are immutable.
- Only one version per name should be is_active=True at any time (the
  "current edition being sold"). Enforced by activate / deactivate endpoints.
- PackageItem rows store denormalised snapshots of the exam item's key fields
  at the moment the version is created, so historical records stay accurate
  even when ExamItem data is later updated.

RBAC
----
  Write: admin, clinic_staff
  Read:  all authenticated users
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select, func

from pydantic import BaseModel

from app.database import get_db
from app.models.exam import ExamItem, Package, PackageItem
from app.models.user import User
from app.core.dependencies import get_current_user, require_role
from app.schemas.exam import (
    PackageCreate,
    PackageNewVersionRequest,
    PackageBrief,
    PackageResponse,
    PackageDiffResponse,
    DiffItem,
    ChangedItem,
    MetadataChange,
)


class PackageItemAddRequest(BaseModel):
    exam_item_id: int
    is_required: bool = True

router = APIRouter(prefix="/packages", tags=["packages"])

_WRITERS = ("admin", "clinic_staff")

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_package(db: Session, package_id: int) -> Package:
    pkg = db.execute(
        select(Package)
        .where(Package.id == package_id)
        .options(selectinload(Package.items).selectinload(PackageItem.exam_item))
    ).scalar_one_or_none()
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")
    return pkg


def _resolve_exam_items(
    db: Session,
    item_specs: list,
) -> dict[int, ExamItem]:
    """
    Fetch all requested ExamItems in one query and validate they exist and are active.
    Returns {exam_item_id: ExamItem}.
    """
    ids = [s.exam_item_id for s in item_specs]
    rows = db.execute(select(ExamItem).where(ExamItem.id.in_(ids))).scalars().all()
    found = {r.id: r for r in rows}

    missing = set(ids) - set(found.keys())
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Exam item IDs not found: {sorted(missing)}",
        )

    inactive = [eid for eid, ei in found.items() if not ei.is_active]
    if inactive:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Exam items are inactive and cannot be added to a package: {sorted(inactive)}",
        )
    return found


def _build_ref_range_snapshot(ei: ExamItem) -> str | None:
    if ei.ref_range_text:
        return ei.ref_range_text
    lo, hi = ei.ref_range_min, ei.ref_range_max
    if lo is not None and hi is not None:
        return f"{lo} – {hi}"
    if lo is not None:
        return f">= {lo}"
    if hi is not None:
        return f"<= {hi}"
    return None


def _build_package_items(
    package: Package,
    item_specs: list,
    exam_items: dict[int, ExamItem],
) -> None:
    """Attach PackageItem rows (with snapshots) to *package*."""
    for spec in item_specs:
        ei = exam_items[spec.exam_item_id]
        pi = PackageItem(
            package_id=package.id,
            exam_item_id=ei.id,
            is_required=spec.is_required,
            item_code_snapshot=ei.code,
            item_name_snapshot=ei.name,
            unit_snapshot=ei.unit,
            ref_range_snapshot=_build_ref_range_snapshot(ei),
            collection_method_snapshot=ei.collection_method,
        )
        package.items.append(pi)


def _next_version(db: Session, name: str) -> int:
    max_ver = db.execute(
        select(func.max(Package.version)).where(Package.name == name)
    ).scalar()
    return (max_ver or 0) + 1


def _deactivate_other_versions(db: Session, name: str, keep_id: int) -> None:
    """Set is_active=False for all versions of *name* except *keep_id*."""
    others = db.execute(
        select(Package).where(Package.name == name, Package.id != keep_id)
    ).scalars().all()
    for pkg in others:
        pkg.is_active = False


def _package_to_brief(pkg: Package) -> PackageBrief:
    return PackageBrief(
        id=pkg.id,
        name=pkg.name,
        version=pkg.version,
        price=pkg.price,
        validity_window_days=pkg.validity_window_days,
        is_active=pkg.is_active,
        created_at=pkg.created_at,
        item_count=len(pkg.items),
    )


# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------

def _compute_diff(pkg_a: Package, pkg_b: Package) -> PackageDiffResponse:
    # Metadata fields to compare
    meta_fields = ["name", "description", "price", "validity_window_days"]
    meta_changes: list[MetadataChange] = []
    for field in meta_fields:
        va = getattr(pkg_a, field)
        vb = getattr(pkg_b, field)
        # Normalise Decimal for comparison
        if isinstance(va, Decimal):
            va = float(va)
        if isinstance(vb, Decimal):
            vb = float(vb)
        if va != vb:
            meta_changes.append(MetadataChange(field=field, from_value=va, to_value=vb))

    # Index items by exam_item_id
    a_items: dict[int, PackageItem] = {pi.exam_item_id: pi for pi in pkg_a.items}
    b_items: dict[int, PackageItem] = {pi.exam_item_id: pi for pi in pkg_b.items}

    a_ids = set(a_items)
    b_ids = set(b_items)

    added: list[DiffItem] = []
    for eid in b_ids - a_ids:
        pi = b_items[eid]
        added.append(DiffItem(
            exam_item_id=eid,
            code=pi.item_code_snapshot,
            name=pi.item_name_snapshot,
        ))

    removed: list[DiffItem] = []
    for eid in a_ids - b_ids:
        pi = a_items[eid]
        removed.append(DiffItem(
            exam_item_id=eid,
            code=pi.item_code_snapshot,
            name=pi.item_name_snapshot,
        ))

    changed: list[ChangedItem] = []
    for eid in a_ids & b_ids:
        pa, pb = a_items[eid], b_items[eid]
        item_changes: dict[str, dict[str, Any]] = {}
        snapshot_fields = [
            "is_required",
            "item_code_snapshot",
            "item_name_snapshot",
            "unit_snapshot",
            "ref_range_snapshot",
            "collection_method_snapshot",
        ]
        for f in snapshot_fields:
            va, vb = getattr(pa, f), getattr(pb, f)
            if va != vb:
                item_changes[f] = {"from": va, "to": vb}
        if item_changes:
            changed.append(ChangedItem(
                exam_item_id=eid,
                code=pb.item_code_snapshot,
                name=pb.item_name_snapshot,
                changes=item_changes,
            ))

    return PackageDiffResponse(
        from_version=pkg_a.version,
        to_version=pkg_b.version,
        metadata_changes=meta_changes,
        items_added=sorted(added, key=lambda x: x.code),
        items_removed=sorted(removed, key=lambda x: x.code),
        items_changed=sorted(changed, key=lambda x: x.code),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
def create_package(
    payload: PackageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """
    Create package version 1.
    The package starts as inactive; call /activate to make it the
    edition that is currently sold.
    """
    # Check name doesn't already exist
    existing = db.execute(
        select(Package).where(Package.name == payload.name)
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Package '{payload.name}' already exists "
                f"(latest version={existing.version}). "
                "Use POST /packages/{id}/new-version to add a new version."
            ),
        )

    exam_items = _resolve_exam_items(db, payload.items)

    pkg = Package(
        name=payload.name.strip(),
        description=payload.description,
        version=1,
        price=payload.price,
        validity_window_days=payload.validity_window_days,
        is_active=False,
        created_by=current_user.id,
    )
    db.add(pkg)
    db.flush()  # get pkg.id before building items

    _build_package_items(pkg, payload.items, exam_items)

    db.commit()
    db.refresh(pkg)
    return pkg


@router.get("", response_model=list[PackageBrief])
def list_packages(
    active_only: bool = Query(default=False, description="Only show is_active=True versions"),
    name: str | None = Query(default=None, max_length=255, description="Filter by package name"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """
    List packages.  By default returns all versions of all packages.
    Use active_only=true to see only the editions currently being sold.
    """
    q = select(Package).options(selectinload(Package.items))
    if active_only:
        q = q.where(Package.is_active == True)  # noqa: E712
    if name:
        q = q.where(Package.name.ilike(f"%{name}%"))
    q = q.order_by(Package.name, Package.version.desc()).offset(skip).limit(limit)
    pkgs = db.execute(q).scalars().all()
    return [_package_to_brief(p) for p in pkgs]


@router.get("/{package_id}", response_model=PackageResponse)
def get_package(
    package_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """Retrieve a single package version with its full item list."""
    return _load_package(db, package_id)


@router.get("/{package_id}/versions", response_model=list[PackageBrief])
def list_package_versions(
    package_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Return every version of the same package name (identified by package_id).
    Useful to see the version history before selecting which edition to activate.
    """
    pkg = _load_package(db, package_id)
    siblings = db.execute(
        select(Package)
        .where(Package.name == pkg.name)
        .options(selectinload(Package.items))
        .order_by(Package.version)
    ).scalars().all()
    return [_package_to_brief(p) for p in siblings]


@router.post("/{package_id}/new-version", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
def create_new_version(
    package_id: int,
    payload: PackageNewVersionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """
    Bump a package to a new version by providing what changed.

    Rules:
    - The original version row is never modified (immutable history).
    - A new row is inserted with version = max(existing) + 1.
    - Fields not supplied in the payload carry over from the source version.
    - At least one field must differ from the source.
    - The new version starts inactive; activate it explicitly when ready.
    """
    source = _load_package(db, package_id)

    # Resolve new items or carry over from source
    new_item_specs = payload.items if payload.items is not None else [
        type("Spec", (), {"exam_item_id": pi.exam_item_id, "is_required": pi.is_required})()
        for pi in source.items
    ]
    if not new_item_specs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A package must contain at least one item",
        )

    exam_items = _resolve_exam_items(db, new_item_specs)

    # Determine effective values (carry over if not supplied)
    new_description = payload.description if payload.description is not None else source.description
    new_price = payload.price if payload.price is not None else source.price
    new_validity = payload.validity_window_days if payload.validity_window_days is not None else source.validity_window_days

    # Guard: require at least one actual change
    source_item_map = {pi.exam_item_id: pi.is_required for pi in source.items}
    new_item_map = {s.exam_item_id: s.is_required for s in new_item_specs}

    nothing_changed = (
        new_description == source.description
        and Decimal(str(new_price)) == Decimal(str(source.price))
        and new_validity == source.validity_window_days
        and source_item_map == new_item_map
    )
    if nothing_changed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No changes detected. The new version would be identical to the source.",
        )

    next_ver = _next_version(db, source.name)

    new_pkg = Package(
        name=source.name,
        description=new_description,
        version=next_ver,
        price=new_price,
        validity_window_days=new_validity,
        is_active=False,
        created_by=current_user.id,
    )
    db.add(new_pkg)
    db.flush()

    _build_package_items(new_pkg, new_item_specs, exam_items)

    db.commit()
    db.refresh(new_pkg)
    return new_pkg


@router.get("/{package_id}/diff/{other_id}", response_model=PackageDiffResponse)
def diff_versions(
    package_id: int,
    other_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Show what changed between two package versions.

    Returns metadata changes (name, price, validity) plus item-level
    additions, removals, and modifications (e.g. required → optional).

    Tip: package_id = older version, other_id = newer version to read
    the diff in chronological order.
    """
    if package_id == other_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="package_id and other_id must be different",
        )
    pkg_a = _load_package(db, package_id)
    pkg_b = _load_package(db, other_id)

    # Both must belong to the same package name for a meaningful diff
    if pkg_a.name != pkg_b.name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Packages belong to different names "
                f"('{pkg_a.name}' vs '{pkg_b.name}'). "
                "Cross-package diff is not supported."
            ),
        )

    return _compute_diff(pkg_a, pkg_b)


@router.patch("/{package_id}/activate", response_model=PackageResponse)
def activate_package(
    package_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(*_WRITERS)),
):
    """
    Mark this version as the active edition being sold.

    All other versions of the same package name are automatically
    deactivated so only one edition is ever "current" at a time.

    This is the confirmation step that a specific version is correct
    and should be offered to patients / customers.
    """
    pkg = _load_package(db, package_id)

    if pkg.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package version is already active",
        )
    if not pkg.items:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot activate a package with no items",
        )

    _deactivate_other_versions(db, pkg.name, keep_id=pkg.id)
    pkg.is_active = True

    db.commit()
    db.refresh(pkg)
    return pkg


@router.patch("/{package_id}/deactivate", response_model=PackageResponse)
def deactivate_package(
    package_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    """
    Deactivate a package version (admin only).
    The package is no longer offered for new orders but historical records
    that reference it are unaffected.
    """
    pkg = _load_package(db, package_id)

    if not pkg.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package version is already inactive",
        )

    pkg.is_active = False
    db.commit()
    db.refresh(pkg)
    return pkg


@router.post("/{package_id}/items", response_model=PackageResponse, status_code=status.HTTP_201_CREATED)
def add_item_to_package(
    package_id: int,
    payload: "PackageItemAddRequest",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """
    Add an exam item to a package by creating a new version automatically.
    The new version is a copy of the source with the extra item appended.
    The new version starts inactive.
    """
    from app.schemas.exam import PackageItemIn  # local import avoids circular

    source = _load_package(db, package_id)

    # Check item isn't already in this version
    existing_ids = {pi.exam_item_id for pi in source.items}
    if payload.exam_item_id in existing_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Exam item {payload.exam_item_id} is already in package version {source.version}",
        )

    new_specs = [
        PackageItemIn(exam_item_id=pi.exam_item_id, is_required=pi.is_required)
        for pi in source.items
    ] + [PackageItemIn(exam_item_id=payload.exam_item_id, is_required=payload.is_required)]

    exam_items = _resolve_exam_items(db, new_specs)
    next_ver = _next_version(db, source.name)

    new_pkg = Package(
        name=source.name,
        description=source.description,
        version=next_ver,
        price=source.price,
        validity_window_days=source.validity_window_days,
        is_active=False,
        created_by=current_user.id,
    )
    db.add(new_pkg)
    db.flush()
    _build_package_items(new_pkg, new_specs, exam_items)
    db.commit()
    db.refresh(new_pkg)
    return new_pkg


@router.delete("/{package_id}/items/{exam_item_id}", response_model=PackageResponse)
def remove_item_from_package(
    package_id: int,
    exam_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_WRITERS)),
):
    """
    Remove an exam item from a package by creating a new version automatically.
    The new version is a copy of the source with the specified item omitted.
    The new version starts inactive.
    Requires at least one item to remain after removal.
    """
    from app.schemas.exam import PackageItemIn

    source = _load_package(db, package_id)

    existing_ids = {pi.exam_item_id for pi in source.items}
    if exam_item_id not in existing_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Exam item {exam_item_id} is not in package version {source.version}",
        )

    new_specs = [
        PackageItemIn(exam_item_id=pi.exam_item_id, is_required=pi.is_required)
        for pi in source.items
        if pi.exam_item_id != exam_item_id
    ]
    if not new_specs:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot remove the last item from a package",
        )

    exam_items = _resolve_exam_items(db, new_specs)
    next_ver = _next_version(db, source.name)

    new_pkg = Package(
        name=source.name,
        description=source.description,
        version=next_ver,
        price=source.price,
        validity_window_days=source.validity_window_days,
        is_active=False,
        created_by=current_user.id,
    )
    db.add(new_pkg)
    db.flush()
    _build_package_items(new_pkg, new_specs, exam_items)
    db.commit()
    db.refresh(new_pkg)
    return new_pkg


