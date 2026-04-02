from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.models.cms import CMSPageStatus, SitemapChangefreq, MAX_PAGE_REVISIONS


# ---------------------------------------------------------------------------
# Page type tags (clinic-specific content categories)
# ---------------------------------------------------------------------------
class CMSPageType(str, Enum):
    notice = "notice"                   # clinic operational notices
    education = "education"             # traceability / agricultural education
    policy = "policy"                   # policies and procedures
    announcement = "announcement"       # general announcements
    faq = "faq"                         # frequently asked questions
    general = "general"                 # uncategorised


# ---------------------------------------------------------------------------
# Create / update
# ---------------------------------------------------------------------------

class CMSPageCreate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=500)]
    slug: Annotated[str, Field(min_length=1, max_length=500,
                                description="URL-safe identifier; auto-generated from title if omitted")]
    content: str = ""
    page_type: CMSPageType = CMSPageType.general

    # Multi-store / multilingual
    store_id: str = Field(default="default", max_length=100)
    locale: str = Field(default="en", max_length=10)

    # SEO
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)
    seo_keywords: str | None = Field(
        default=None,
        description="Comma-separated keywords, e.g. 'traceability,clinic,health'",
    )

    # Sitemap
    is_in_sitemap: bool = True
    sitemap_priority: Annotated[Decimal, Field(ge=0, le=1, decimal_places=1)] = Decimal("0.5")
    sitemap_changefreq: SitemapChangefreq = SitemapChangefreq.monthly

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens only (e.g. 'clinic-notice')"
            )
        return v


class CMSPageUpdate(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    slug: Annotated[str, Field(min_length=1, max_length=500)] | None = None
    content: str | None = None
    page_type: CMSPageType | None = None
    store_id: str | None = Field(default=None, max_length=100)
    locale: str | None = Field(default=None, max_length=10)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)
    seo_keywords: str | None = None
    is_in_sitemap: bool | None = None
    sitemap_priority: Annotated[Decimal, Field(ge=0, le=1, decimal_places=1)] | None = None
    sitemap_changefreq: SitemapChangefreq | None = None
    change_note: str | None = Field(
        default=None, max_length=500,
        description="Reason for this edit; stored in revision history",
    )

    @field_validator("slug")
    @classmethod
    def validate_slug(cls, v: str | None) -> str | None:
        if v is not None and not re.match(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", v):
            raise ValueError(
                "Slug must be lowercase alphanumeric with hyphens only"
            )
        return v


# ---------------------------------------------------------------------------
# Revision response
# ---------------------------------------------------------------------------

class CMSPageRevisionResponse(BaseModel):
    id: int
    page_id: int
    revision_number: int
    title_snapshot: str
    slug_snapshot: str | None
    content_snapshot: str
    status_snapshot: str
    store_id_snapshot: str | None
    locale_snapshot: str | None
    seo_title_snapshot: str | None
    seo_description_snapshot: str | None
    seo_keywords_snapshot: str | None
    sitemap_priority_snapshot: float | None
    sitemap_changefreq_snapshot: str | None
    is_in_sitemap_snapshot: bool | None
    changed_by: int
    change_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CMSPageRevisionBrief(BaseModel):
    id: int
    revision_number: int
    title_snapshot: str
    status_snapshot: str
    changed_by: int
    change_note: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Page responses
# ---------------------------------------------------------------------------

class CMSPageResponse(BaseModel):
    id: int
    title: str
    slug: str
    content: str
    page_type: str | None
    status: CMSPageStatus
    store_id: str
    locale: str
    seo_title: str | None
    seo_description: str | None
    seo_keywords: str | None
    is_in_sitemap: bool
    sitemap_priority: Decimal
    sitemap_changefreq: SitemapChangefreq
    current_revision: int
    created_by: int
    published_by: int | None
    reviewed_by: int | None
    published_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CMSPageBrief(BaseModel):
    """Lightweight listing item."""
    id: int
    title: str
    slug: str
    page_type: str | None
    status: CMSPageStatus
    store_id: str
    locale: str
    current_revision: int
    created_by: int
    published_at: datetime | None
    updated_at: datetime

    model_config = {"from_attributes": True}


class CMSPagePreviewResponse(BaseModel):
    """Preview envelope — same as CMSPageResponse with a preview flag."""
    page: CMSPageResponse
    is_preview: bool = True
    preview_note: str = "This page is not published. Content shown for preview only."


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class WorkflowTransitionRequest(BaseModel):
    note: str | None = Field(
        default=None, max_length=500,
        description="Optional note recorded in the revision history for this transition",
    )


# ---------------------------------------------------------------------------
# Sitemap
# ---------------------------------------------------------------------------

class SitemapEntry(BaseModel):
    loc: str           # full URL (e.g. /cms/pages/{slug})
    slug: str
    store_id: str
    locale: str
    priority: float
    changefreq: str
    lastmod: datetime


# ---------------------------------------------------------------------------
# CSV Export row
# ---------------------------------------------------------------------------

class CMSExportRow(BaseModel):
    id: int
    title: str
    slug: str
    page_type: str | None
    status: str
    store_id: str
    locale: str
    seo_title: str | None
    seo_description: str | None
    sitemap_priority: str
    is_in_sitemap: bool
    current_revision: int
    created_by: int
    created_at: str
    published_at: str | None
    updated_at: str
