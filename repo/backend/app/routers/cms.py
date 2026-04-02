"""CMS router — clinic notices, education pages, policies, announcements.

Workflow:  draft → review → published → archived
           review → draft (reject)
           archived → draft (restore)

Revision cap: up to 30 revisions per page; oldest pruned after each save.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cms import CMSPage, CMSPageRevision, CMSPageStatus, MAX_PAGE_REVISIONS
from app.models.user import User
from app.core.dependencies import get_current_user, require_role
from app.schemas.cms import (
    CMSPageBrief,
    CMSPageCreate,
    CMSPagePreviewResponse,
    CMSPageResponse,
    CMSPageRevisionBrief,
    CMSPageRevisionResponse,
    CMSPageUpdate,
    SitemapEntry,
    WorkflowTransitionRequest,
    CMSExportRow,
)

router = APIRouter(prefix="/cms", tags=["cms"])

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STAFF_ROLES = ("admin", "clinic_staff", "catalog_manager")


def _get_page_or_404(page_id: int, db: Session) -> CMSPage:
    page = db.execute(select(CMSPage).where(CMSPage.id == page_id)).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


def _snapshot_revision(page: CMSPage, editor_id: int, note: str | None, db: Session) -> None:
    """Create a revision snapshot, then prune oldest if cap exceeded."""
    page.current_revision += 1
    rev = CMSPageRevision(
        page_id=page.id,
        revision_number=page.current_revision,
        title_snapshot=page.title,
        slug_snapshot=page.slug,
        content_snapshot=page.content,
        status_snapshot=page.status.value,
        store_id_snapshot=page.store_id,
        locale_snapshot=page.locale,
        seo_title_snapshot=page.seo_title,
        seo_description_snapshot=page.seo_description,
        seo_keywords_snapshot=page.seo_keywords,
        sitemap_priority_snapshot=float(page.sitemap_priority),
        sitemap_changefreq_snapshot=page.sitemap_changefreq.value if page.sitemap_changefreq else None,
        is_in_sitemap_snapshot=page.is_in_sitemap,
        changed_by=editor_id,
        change_note=note,
    )
    db.add(rev)
    db.flush()  # assign rev.id before pruning

    # Prune oldest revisions beyond the cap
    all_revs = db.execute(
        select(CMSPageRevision)
        .where(CMSPageRevision.page_id == page.id)
        .order_by(CMSPageRevision.revision_number)
    ).scalars().all()
    if len(all_revs) > MAX_PAGE_REVISIONS:
        for old_rev in all_revs[: len(all_revs) - MAX_PAGE_REVISIONS]:
            db.delete(old_rev)


def _check_slug_unique(slug: str, store_id: str, locale: str, db: Session, exclude_id: int | None = None) -> None:
    q = select(CMSPage).where(
        and_(
            CMSPage.slug == slug,
            CMSPage.store_id == store_id,
            CMSPage.locale == locale,
        )
    )
    if exclude_id is not None:
        q = q.where(CMSPage.id != exclude_id)
    existing = db.execute(q).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slug '{slug}' already exists for store '{store_id}' / locale '{locale}'",
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.post("/pages", response_model=CMSPageResponse, status_code=status.HTTP_201_CREATED)
def create_page(
    payload: CMSPageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    _check_slug_unique(payload.slug, payload.store_id, payload.locale, db)

    page = CMSPage(
        title=payload.title,
        slug=payload.slug,
        content=payload.content,
        page_type=payload.page_type.value if payload.page_type else None,
        status=CMSPageStatus.draft,
        store_id=payload.store_id,
        locale=payload.locale,
        seo_title=payload.seo_title,
        seo_description=payload.seo_description,
        seo_keywords=payload.seo_keywords,
        is_in_sitemap=payload.is_in_sitemap,
        sitemap_priority=payload.sitemap_priority,
        sitemap_changefreq=payload.sitemap_changefreq,
        created_by=current_user.id,
        current_revision=0,
    )
    db.add(page)
    db.flush()  # get page.id

    _snapshot_revision(page, current_user.id, "Initial creation", db)
    db.commit()
    db.refresh(page)
    return page


@router.get("/pages", response_model=list[CMSPageBrief])
def list_pages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    store_id: Optional[str] = Query(None),
    locale: Optional[str] = Query(None),
    page_type: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
):
    is_staff = current_user.role.value in _STAFF_ROLES
    q = select(CMSPage)

    if not is_staff:
        # Public: published only
        q = q.where(CMSPage.status == CMSPageStatus.published)
    elif status_filter:
        try:
            q = q.where(CMSPage.status == CMSPageStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'")

    if store_id:
        q = q.where(CMSPage.store_id == store_id)
    if locale:
        q = q.where(CMSPage.locale == locale)
    if page_type:
        q = q.where(CMSPage.page_type == page_type)
    if search:
        term = f"%{search}%"
        q = q.where(or_(CMSPage.title.ilike(term), CMSPage.slug.ilike(term)))

    q = q.order_by(CMSPage.updated_at.desc()).offset(skip).limit(limit)
    pages = db.execute(q).scalars().all()
    return pages


@router.get("/pages/export")
def export_pages_csv(
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
    store_id: Optional[str] = Query(None),
    locale: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    """Export all (or filtered) CMS pages as CSV — admin only."""
    q = select(CMSPage)
    if store_id:
        q = q.where(CMSPage.store_id == store_id)
    if locale:
        q = q.where(CMSPage.locale == locale)
    if status_filter:
        try:
            q = q.where(CMSPage.status == CMSPageStatus(status_filter))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'")

    pages = db.execute(q.order_by(CMSPage.id)).scalars().all()

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(CMSExportRow.model_fields.keys()))
    writer.writeheader()
    for p in pages:
        writer.writerow(
            CMSExportRow(
                id=p.id,
                title=p.title,
                slug=p.slug,
                page_type=p.page_type,
                status=p.status.value,
                store_id=p.store_id,
                locale=p.locale,
                seo_title=p.seo_title,
                seo_description=p.seo_description,
                sitemap_priority=str(p.sitemap_priority),
                is_in_sitemap=p.is_in_sitemap,
                current_revision=p.current_revision,
                created_by=p.created_by,
                created_at=p.created_at.isoformat(),
                published_at=p.published_at.isoformat() if p.published_at else None,
                updated_at=p.updated_at.isoformat(),
            ).model_dump()
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=cms_pages.csv"},
    )


@router.get("/pages/{page_id}", response_model=CMSPageResponse)
def get_page_by_id(
    page_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = _get_page_or_404(page_id, db)
    is_staff = current_user.role.value in _STAFF_ROLES
    if not is_staff and page.status != CMSPageStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


@router.get("/pages/by-slug/{slug}", response_model=CMSPageResponse)
def get_page_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    store_id: str = Query("default"),
    locale: str = Query("en"),
):
    page = db.execute(
        select(CMSPage).where(
            and_(
                CMSPage.slug == slug,
                CMSPage.store_id == store_id,
                CMSPage.locale == locale,
            )
        )
    ).scalar_one_or_none()
    if not page:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    is_staff = current_user.role.value in _STAFF_ROLES
    if not is_staff and page.status != CMSPageStatus.published:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
    return page


@router.put("/pages/{page_id}", response_model=CMSPageResponse)
def update_page(
    page_id: int,
    payload: CMSPageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    page = _get_page_or_404(page_id, db)

    if page.status == CMSPageStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Archived pages cannot be edited. Restore first.",
        )

    updates = payload.model_dump(exclude_none=True, exclude={"change_note"})
    if not updates:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")

    if "slug" in updates:
        new_slug = updates["slug"]
        new_store = updates.get("store_id", page.store_id)
        new_locale = updates.get("locale", page.locale)
        _check_slug_unique(new_slug, new_store, new_locale, db, exclude_id=page_id)

    if "page_type" in updates and updates["page_type"] is not None:
        updates["page_type"] = updates["page_type"].value if hasattr(updates["page_type"], "value") else updates["page_type"]

    for field, value in updates.items():
        setattr(page, field, value)

    _snapshot_revision(page, current_user.id, payload.change_note, db)
    db.commit()
    db.refresh(page)
    return page


@router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(
    page_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin")),
):
    page = _get_page_or_404(page_id, db)
    if page.status == CMSPageStatus.published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published pages cannot be deleted. Archive first.",
        )
    db.delete(page)
    db.commit()


# ---------------------------------------------------------------------------
# Workflow transitions
# ---------------------------------------------------------------------------

@router.post("/pages/{page_id}/submit-review", response_model=CMSPageResponse)
def submit_for_review(
    page_id: int,
    payload: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    page = _get_page_or_404(page_id, db)
    if page.status != CMSPageStatus.draft:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only draft pages can be submitted for review (current: {page.status.value})",
        )
    page.status = CMSPageStatus.review
    _snapshot_revision(page, current_user.id, payload.note or "Submitted for review", db)
    db.commit()
    db.refresh(page)
    return page


@router.post("/pages/{page_id}/approve", response_model=CMSPageResponse)
def approve_page(
    page_id: int,
    payload: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    page = _get_page_or_404(page_id, db)
    if page.status != CMSPageStatus.review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pages in review can be approved (current: {page.status.value})",
        )
    now = datetime.now(timezone.utc)
    page.status = CMSPageStatus.published
    page.reviewed_by = current_user.id
    page.reviewed_at = now
    page.published_by = current_user.id
    page.published_at = now
    _snapshot_revision(page, current_user.id, payload.note or "Approved and published", db)
    db.commit()
    db.refresh(page)
    return page


@router.post("/pages/{page_id}/reject", response_model=CMSPageResponse)
def reject_page(
    page_id: int,
    payload: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    page = _get_page_or_404(page_id, db)
    if page.status != CMSPageStatus.review:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only pages in review can be rejected (current: {page.status.value})",
        )
    page.status = CMSPageStatus.draft
    page.reviewed_by = current_user.id
    page.reviewed_at = datetime.now(timezone.utc)
    _snapshot_revision(page, current_user.id, payload.note or "Rejected — returned to draft", db)
    db.commit()
    db.refresh(page)
    return page


@router.post("/pages/{page_id}/archive", response_model=CMSPageResponse)
def archive_page(
    page_id: int,
    payload: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    page = _get_page_or_404(page_id, db)
    if page.status == CMSPageStatus.archived:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Page is already archived")
    page.status = CMSPageStatus.archived
    _snapshot_revision(page, current_user.id, payload.note or "Archived", db)
    db.commit()
    db.refresh(page)
    return page


@router.post("/pages/{page_id}/restore", response_model=CMSPageResponse)
def restore_page(
    page_id: int,
    payload: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    page = _get_page_or_404(page_id, db)
    if page.status != CMSPageStatus.archived:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Only archived pages can be restored (current: {page.status.value})",
        )
    page.status = CMSPageStatus.draft
    _snapshot_revision(page, current_user.id, payload.note or "Restored from archive", db)
    db.commit()
    db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# Revision management
# ---------------------------------------------------------------------------

@router.get("/pages/{page_id}/revisions", response_model=list[CMSPageRevisionBrief])
def list_revisions(
    page_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    _get_page_or_404(page_id, db)
    revisions = db.execute(
        select(CMSPageRevision)
        .where(CMSPageRevision.page_id == page_id)
        .order_by(CMSPageRevision.revision_number.desc())
    ).scalars().all()
    return revisions


@router.get("/pages/{page_id}/revisions/{revision_number}", response_model=CMSPageRevisionResponse)
def get_revision(
    page_id: int,
    revision_number: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    _get_page_or_404(page_id, db)
    rev = db.execute(
        select(CMSPageRevision).where(
            and_(
                CMSPageRevision.page_id == page_id,
                CMSPageRevision.revision_number == revision_number,
            )
        )
    ).scalar_one_or_none()
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")
    return rev


@router.post("/pages/{page_id}/rollback/{revision_number}", response_model=CMSPageResponse)
def rollback_to_revision(
    page_id: int,
    revision_number: int,
    payload: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    page = _get_page_or_404(page_id, db)
    rev = db.execute(
        select(CMSPageRevision).where(
            and_(
                CMSPageRevision.page_id == page_id,
                CMSPageRevision.revision_number == revision_number,
            )
        )
    ).scalar_one_or_none()
    if not rev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Revision not found")

    # Restore all snapshot fields onto the live page
    page.title = rev.title_snapshot
    page.content = rev.content_snapshot
    if rev.slug_snapshot:
        # Check uniqueness for restored slug only if it differs
        if rev.slug_snapshot != page.slug:
            restore_store = rev.store_id_snapshot or page.store_id
            restore_locale = rev.locale_snapshot or page.locale
            _check_slug_unique(rev.slug_snapshot, restore_store, restore_locale, db, exclude_id=page_id)
        page.slug = rev.slug_snapshot
    if rev.store_id_snapshot:
        page.store_id = rev.store_id_snapshot
    if rev.locale_snapshot:
        page.locale = rev.locale_snapshot
    page.seo_title = rev.seo_title_snapshot
    page.seo_description = rev.seo_description_snapshot
    page.seo_keywords = rev.seo_keywords_snapshot
    if rev.sitemap_priority_snapshot is not None:
        page.sitemap_priority = rev.sitemap_priority_snapshot
    if rev.sitemap_changefreq_snapshot:
        from app.models.cms import SitemapChangefreq
        page.sitemap_changefreq = SitemapChangefreq(rev.sitemap_changefreq_snapshot)
    if rev.is_in_sitemap_snapshot is not None:
        page.is_in_sitemap = rev.is_in_sitemap_snapshot

    # Rollback moves page back to draft regardless of previous status
    page.status = CMSPageStatus.draft

    note = payload.note or f"Rolled back to revision {revision_number}"
    _snapshot_revision(page, current_user.id, note, db)
    db.commit()
    db.refresh(page)
    return page


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

@router.get("/pages/{page_id}/preview", response_model=CMSPagePreviewResponse)
def preview_page(
    page_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_role("admin", "clinic_staff", "catalog_manager")),
):
    page = _get_page_or_404(page_id, db)
    return CMSPagePreviewResponse(page=CMSPageResponse.model_validate(page))


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

@router.get("/sitemap.json", response_model=list[SitemapEntry])
def sitemap_json(
    db: Session = Depends(get_db),
    store_id: Optional[str] = Query(None),
    locale: Optional[str] = Query(None),
):
    q = select(CMSPage).where(
        and_(CMSPage.status == CMSPageStatus.published, CMSPage.is_in_sitemap == True)
    )
    if store_id:
        q = q.where(CMSPage.store_id == store_id)
    if locale:
        q = q.where(CMSPage.locale == locale)
    pages = db.execute(q).scalars().all()

    return [
        SitemapEntry(
            loc=f"/cms/pages/{p.slug}",
            slug=p.slug,
            store_id=p.store_id,
            locale=p.locale,
            priority=float(p.sitemap_priority),
            changefreq=p.sitemap_changefreq.value,
            lastmod=p.updated_at,
        )
        for p in pages
    ]


@router.get("/sitemap.xml")
def sitemap_xml(
    db: Session = Depends(get_db),
    store_id: Optional[str] = Query(None),
    locale: Optional[str] = Query(None),
):
    q = select(CMSPage).where(
        and_(CMSPage.status == CMSPageStatus.published, CMSPage.is_in_sitemap == True)
    )
    if store_id:
        q = q.where(CMSPage.store_id == store_id)
    if locale:
        q = q.where(CMSPage.locale == locale)
    pages = db.execute(q).scalars().all()

    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    lines.append('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">')
    for p in pages:
        lastmod = p.updated_at.strftime("%Y-%m-%d")
        lines.append("  <url>")
        lines.append(f"    <loc>/cms/pages/{p.slug}</loc>")
        lines.append(f"    <lastmod>{lastmod}</lastmod>")
        lines.append(f"    <changefreq>{p.sitemap_changefreq.value}</changefreq>")
        lines.append(f"    <priority>{float(p.sitemap_priority):.1f}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    return Response(content="\n".join(lines), media_type="application/xml")
