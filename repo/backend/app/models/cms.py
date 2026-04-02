import enum
from datetime import datetime, timezone
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Boolean, Integer, Numeric,
    Enum as SAEnum, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

# Max revisions to retain per page (oldest pruned beyond this)
MAX_PAGE_REVISIONS = 30


class CMSPageStatus(str, enum.Enum):
    draft = "draft"
    review = "review"        # submitted for editorial review
    published = "published"
    archived = "archived"


class SitemapChangefreq(str, enum.Enum):
    always = "always"
    hourly = "hourly"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"
    never = "never"


class CMSPage(Base):
    """
    A content page with draft → review → published → archived lifecycle.
    Supports multi-store and multilingual variants via (slug, store_id, locale).
    Keeps SEO metadata and sitemap configuration.
    Changes are versioned in CMSPageRevision (max 30 per page).
    """
    __tablename__ = "cms_pages"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    slug: Mapped[str] = mapped_column(String(500), index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    page_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Workflow state
    status: Mapped[CMSPageStatus] = mapped_column(
        SAEnum(CMSPageStatus), nullable=False, default=CMSPageStatus.draft
    )

    # Multi-store / multilingual
    store_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    # SEO metadata
    seo_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_keywords: Mapped[str | None] = mapped_column(Text, nullable=True)       # comma-separated

    # Sitemap
    is_in_sitemap: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sitemap_priority: Mapped[float] = mapped_column(
        Numeric(2, 1), nullable=False, default=0.5
    )  # 0.0 – 1.0
    sitemap_changefreq: Mapped[SitemapChangefreq] = mapped_column(
        SAEnum(SitemapChangefreq), nullable=False, default=SitemapChangefreq.monthly
    )

    # Revision tracking
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Authorship
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    published_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    publisher = relationship("User", foreign_keys=[published_by])
    reviewer_user = relationship("User", foreign_keys=[reviewed_by])
    revisions = relationship(
        "CMSPageRevision",
        back_populates="page",
        cascade="all, delete-orphan",
        order_by="CMSPageRevision.revision_number",
    )

    __table_args__ = (
        # slug must be unique per store + locale combination
        UniqueConstraint("slug", "store_id", "locale", name="uq_cms_pages_slug_store_locale"),
        CheckConstraint(
            "sitemap_priority >= 0.0 AND sitemap_priority <= 1.0",
            name="ck_cms_pages_sitemap_priority_range",
        ),
    )


class CMSPageRevision(Base):
    """
    Immutable snapshot of a CMSPage at a point in time.
    Enables rollback to any of the last 30 revisions.
    Pruning of older revisions is handled at the application layer.
    """
    __tablename__ = "cms_page_revisions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    page_id: Mapped[int] = mapped_column(
        ForeignKey("cms_pages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Complete content snapshot (all fields needed for a lossless rollback)
    title_snapshot: Mapped[str] = mapped_column(String(500), nullable=False)
    slug_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    status_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    store_id_snapshot: Mapped[str | None] = mapped_column(String(100), nullable=True)
    locale_snapshot: Mapped[str | None] = mapped_column(String(10), nullable=True)
    seo_title_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)
    seo_description_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    seo_keywords_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    sitemap_priority_snapshot: Mapped[float | None] = mapped_column(Numeric(2, 1), nullable=True)
    sitemap_changefreq_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_in_sitemap_snapshot: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Who made the change and why
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    change_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    page = relationship("CMSPage", back_populates="revisions")
    editor = relationship("User", foreign_keys=[changed_by])

    __table_args__ = (
        UniqueConstraint("page_id", "revision_number", name="uq_cms_revisions_page_rev"),
        CheckConstraint("revision_number >= 1", name="ck_cms_revisions_number_positive"),
    )
