"""
Offline file validation utilities
===================================
No cloud calls, no external scanning.  All checks are done locally:

  1. Magic-byte sniffing — verify the actual file content matches the
     declared Content-Type before accepting the upload.
  2. SHA-256 fingerprint — computed from the raw bytes and stored in the
     database so integrity can be verified at any time without network access.

Supported MIME types mirror app.models.catalog.ALLOWED_MIME_TYPES.
"""
import hashlib
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Magic-byte signatures
# Each entry: (mime_type, sequence_of_(offset, bytes_to_match))
# ---------------------------------------------------------------------------
_SIGNATURES: list[tuple[str, list[tuple[int, bytes]]]] = [
    # Images
    ("image/jpeg",  [(0, b"\xff\xd8\xff")]),
    ("image/png",   [(0, b"\x89PNG\r\n\x1a\n")]),
    ("image/gif",   [(0, b"GIF87a"), (0, b"GIF89a")]),
    ("image/webp",  [(0, b"RIFF"), (8, b"WEBP")]),

    # PDF
    ("application/pdf", [(0, b"%PDF")]),

    # Office Open XML (DOCX / XLSX) — both are ZIP with PK header
    (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        [(0, b"PK\x03\x04")],
    ),
    (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        [(0, b"PK\x03\x04")],
    ),

    # Legacy Office (DOC / XLS) — OLE2 compound document
    ("application/msword",            [(0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")]),
    ("application/vnd.ms-excel",      [(0, b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")]),

    # Plain text / CSV — no reliable magic bytes; validated by declared MIME only
    ("text/plain", []),
    ("text/csv",   []),
]

# Build lookup: mime_type -> list of candidate signature sets
_MIME_SIGS: dict[str, list[list[tuple[int, bytes]]]] = {}
for _mime, _sigs in _SIGNATURES:
    _MIME_SIGS.setdefault(_mime, []).append(_sigs)


class ValidationError(ValueError):
    """Raised when a file fails MIME or size validation."""


class FileFingerprint(NamedTuple):
    sha256: str        # lowercase hex digest
    size_bytes: int


def compute_fingerprint(data: bytes) -> FileFingerprint:
    """Return the SHA-256 hex digest and byte length of *data*."""
    return FileFingerprint(
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )


def _check_magic(data: bytes, mime: str) -> bool:
    """
    Return True if *data* matches at least one known signature for *mime*.
    For text types (no magic bytes defined) always return True — the
    declared MIME is accepted as-is after the size check.
    """
    candidate_sets = _MIME_SIGS.get(mime)
    if candidate_sets is None:
        # Unknown MIME — reject
        return False

    for sig_set in candidate_sets:
        if not sig_set:
            # Empty sig list = text/* — no magic bytes to check
            return True
        if all(data[offset: offset + len(seq)] == seq for offset, seq in sig_set):
            return True

    return False


def validate_upload(
    data: bytes,
    declared_mime: str,
    original_filename: str,
    allowed_mimes: set[str],
    max_size_bytes: int,
) -> FileFingerprint:
    """
    Validate an uploaded file fully offline.

    Checks (in order):
      1. Declared MIME is in the allow-list.
      2. File size does not exceed *max_size_bytes*.
      3. File is not empty.
      4. Magic bytes match the declared MIME (skipped for text/plain and text/csv).

    Returns a FileFingerprint on success; raises ValidationError on failure.
    """
    # 1. Allow-list check
    normalised = declared_mime.split(";")[0].strip().lower()
    if normalised not in allowed_mimes:
        raise ValidationError(
            f"File type '{normalised}' is not allowed. "
            f"Accepted types: {', '.join(sorted(allowed_mimes))}"
        )

    # 2. Size check
    size = len(data)
    if size > max_size_bytes:
        raise ValidationError(
            f"File '{original_filename}' is {size:,} bytes which exceeds the "
            f"{max_size_bytes // (1024 * 1024)} MB limit."
        )

    # 3. Empty check
    if size == 0:
        raise ValidationError(f"File '{original_filename}' is empty.")

    # 4. Magic-byte check
    if not _check_magic(data, normalised):
        raise ValidationError(
            f"File content does not match declared type '{normalised}'. "
            "The file may be corrupt or its extension has been spoofed."
        )

    return compute_fingerprint(data)


def verify_file_integrity(data: bytes, expected_sha256: str) -> bool:
    """
    Re-compute the SHA-256 of *data* and compare to the stored fingerprint.
    Returns True if they match, False if the file has been modified.
    """
    return hashlib.sha256(data).hexdigest() == expected_sha256.lower()
