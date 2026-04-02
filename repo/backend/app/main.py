"""TraceCare Offline Compliance Portal — FastAPI application entry point.

Security features wired here:
  • OfflineSecurityMiddleware — private-IP enforcement + hardened response headers
  • SensitiveDataFilter      — token / password redaction from all log sinks
  • CORS restricted to localhost origins only (no external access)
"""
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.core.log_filter import configure_secure_logging
from app.core.security_middleware import OfflineSecurityMiddleware
from app.routers import (
    admin, audit, auth, catalog, cms, exam_items, exams,
    messages, notifications, packages, products, reviews, users,
)

# ---------------------------------------------------------------------------
# Logging — install redaction filter before anything else logs
# ---------------------------------------------------------------------------
configure_secure_logging()

logger = logging.getLogger("tracecare")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="TraceCare Offline Compliance Portal",
    description="Fully offline/on-prem compliance management system",
    version="1.0.0",
    # Disable OpenAPI in production if desired:
    # openapi_url=None,
)

# ---------------------------------------------------------------------------
# Security middleware (runs before CORS)
# ---------------------------------------------------------------------------
app.add_middleware(
    OfflineSecurityMiddleware,
    enforce_local_only=True,  # Set False only for dev/test against public IP
)

# ---------------------------------------------------------------------------
# CORS — localhost only (belt-and-suspenders alongside IP enforcement)
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
_API = "/api"
app.include_router(auth.router,          prefix=_API)
app.include_router(users.router,         prefix=_API)
app.include_router(exam_items.router,    prefix=_API)
app.include_router(packages.router,      prefix=_API)
app.include_router(exams.router,         prefix=_API)
app.include_router(products.router,      prefix=_API)
app.include_router(catalog.router,       prefix=_API)
app.include_router(messages.router,      prefix=_API)
app.include_router(notifications.router, prefix=_API)
app.include_router(cms.router,           prefix=_API)
app.include_router(reviews.router,       prefix=_API)
app.include_router(admin.router,         prefix=_API)
app.include_router(audit.router,         prefix=_API)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "TraceCare Compliance Portal"}


# ---------------------------------------------------------------------------
# Static files (uploaded attachments — local filesystem, auth on /catalog/...)
# ---------------------------------------------------------------------------
app.mount(
    "/uploads",
    StaticFiles(directory=str(settings.attachments_path.parent)),
    name="uploads",
)
