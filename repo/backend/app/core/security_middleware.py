"""ASGI security middleware for the TraceCare offline/on-prem deployment.

Responsibilities:
  1. Localhost / private-network enforcement — reject requests from public IPs.
  2. Inject hardened HTTP security headers on every response.
  3. Emit redacted access-log lines (tokens and passwords masked).

The IP allowlist is intentionally broad to cover on-prem LANs:
  127.x.x.x, ::1, 10.x.x.x, 172.16-31.x.x, 192.168.x.x, fd00::/8 (ULA).
If an extra subnet is needed, add it to ALLOWED_NETWORKS below.
"""
from __future__ import annotations

import ipaddress
import logging
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.log_filter import _redact

logger = logging.getLogger("tracecare.security")

# ---------------------------------------------------------------------------
# Private / loopback network ranges (offline on-prem only)
# ---------------------------------------------------------------------------
_ALLOWED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC-1918 class A
    ipaddress.ip_network("172.16.0.0/12"),      # RFC-1918 class B
    ipaddress.ip_network("192.168.0.0/16"),     # RFC-1918 class C
    ipaddress.ip_network("fc00::/7"),           # IPv6 ULA (fd00::/8 subset)
]


def _is_private(raw_ip: str) -> bool:
    """Return True if *raw_ip* belongs to an allowed private/loopback range."""
    try:
        addr = ipaddress.ip_address(raw_ip)
    except ValueError:
        return False
    return any(addr in net for net in _ALLOWED_NETWORKS)


# ---------------------------------------------------------------------------
# Security response headers
# ---------------------------------------------------------------------------
_SECURITY_HEADERS: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none'"
    ),
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Cache-Control": "no-store",          # don't cache sensitive API responses
    "Strict-Transport-Security": "max-age=0",  # no HTTPS in local deployments
}

# Paths that serve static/public content — relax Cache-Control there
_STATIC_PREFIXES = ("/uploads/",)


class OfflineSecurityMiddleware(BaseHTTPMiddleware):
    """
    Middleware stack:
      request → IP check → handler → inject headers + log → response
    """

    def __init__(self, app, *, enforce_local_only: bool = True) -> None:
        super().__init__(app)
        self.enforce_local_only = enforce_local_only

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        client_ip = request.client.host if request.client else "unknown"

        # ── 1. IP enforcement ────────────────────────────────────────────────
        if self.enforce_local_only and not _is_private(client_ip):
            logger.warning(
                "Blocked request from non-private IP %s → %s %s",
                client_ip,
                request.method,
                request.url.path,
            )
            return JSONResponse(
                status_code=403,
                content={"detail": "Access restricted to local network only."},
                headers={**_SECURITY_HEADERS},
            )

        # ── 2. Call handler ──────────────────────────────────────────────────
        start = time.monotonic()
        response: Response = await call_next(request)
        elapsed_ms = (time.monotonic() - start) * 1000

        # ── 3. Inject security headers ───────────────────────────────────────
        is_static = any(request.url.path.startswith(p) for p in _STATIC_PREFIXES)
        for header, value in _SECURITY_HEADERS.items():
            if is_static and header == "Cache-Control":
                response.headers["Cache-Control"] = "public, max-age=3600"
            else:
                response.headers.setdefault(header, value)

        # Remove headers that leak server info
        response.headers.pop("Server", None)
        response.headers.pop("X-Powered-By", None)

        # ── 4. Redacted access log ───────────────────────────────────────────
        path = _redact(str(request.url.path))
        logger.info(
            "%s %s %s %d %.1fms",
            client_ip,
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )

        return response
