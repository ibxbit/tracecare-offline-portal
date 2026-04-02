"""
Unit tests for app.core.file_utils:
  - compute_fingerprint
  - validate_upload
  - verify_file_integrity
"""
import hashlib

import pytest

from app.core.file_utils import (
    FileFingerprint,
    ValidationError,
    compute_fingerprint,
    validate_upload,
    verify_file_integrity,
)

_ALLOWED = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf", "text/plain", "text/csv",
}
_MAX_SIZE = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# compute_fingerprint
# ---------------------------------------------------------------------------

class TestComputeFingerprint:
    def test_returns_named_tuple(self):
        fp = compute_fingerprint(b"hello")
        assert isinstance(fp, FileFingerprint)

    def test_sha256_correct(self):
        data = b"tracecare"
        expected = hashlib.sha256(data).hexdigest()
        fp = compute_fingerprint(data)
        assert fp.sha256 == expected

    def test_size_correct(self):
        data = b"A" * 42
        fp = compute_fingerprint(data)
        assert fp.size_bytes == 42

    def test_empty_bytes_has_known_hash(self):
        fp = compute_fingerprint(b"")
        assert fp.sha256 == hashlib.sha256(b"").hexdigest()
        assert fp.size_bytes == 0

    def test_sha256_is_lowercase_hex(self):
        fp = compute_fingerprint(b"test")
        assert fp.sha256 == fp.sha256.lower()
        assert len(fp.sha256) == 64


# ---------------------------------------------------------------------------
# validate_upload
# ---------------------------------------------------------------------------

def _jpeg_bytes() -> bytes:
    """Minimal JPEG magic header."""
    return b"\xff\xd8\xff" + b"\x00" * 10

def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 10

def _pdf_bytes() -> bytes:
    return b"%PDF" + b"\x00" * 10

def _text_bytes() -> bytes:
    return b"plain text content here"


class TestValidateUpload:
    def test_valid_jpeg(self):
        fp = validate_upload(_jpeg_bytes(), "image/jpeg", "photo.jpg", _ALLOWED, _MAX_SIZE)
        assert fp.sha256 != ""

    def test_valid_png(self):
        fp = validate_upload(_png_bytes(), "image/png", "img.png", _ALLOWED, _MAX_SIZE)
        assert isinstance(fp, FileFingerprint)

    def test_valid_pdf(self):
        fp = validate_upload(_pdf_bytes(), "application/pdf", "doc.pdf", _ALLOWED, _MAX_SIZE)
        assert fp.size_bytes > 0

    def test_valid_text_no_magic_check(self):
        fp = validate_upload(_text_bytes(), "text/plain", "file.txt", _ALLOWED, _MAX_SIZE)
        assert fp.size_bytes == len(_text_bytes())

    def test_valid_csv(self):
        data = b"col1,col2\nval1,val2"
        fp = validate_upload(data, "text/csv", "data.csv", _ALLOWED, _MAX_SIZE)
        assert fp.size_bytes > 0

    def test_disallowed_mime_raises(self):
        with pytest.raises(ValidationError, match="not allowed"):
            validate_upload(_jpeg_bytes(), "application/exe", "virus.exe", _ALLOWED, _MAX_SIZE)

    def test_file_too_large_raises(self):
        big = b"X" * (10 * 1024 * 1024)  # 10 MB > 5 MB limit
        with pytest.raises(ValidationError, match="exceeds"):
            validate_upload(big, "text/plain", "huge.txt", _ALLOWED, 5 * 1024 * 1024)

    def test_empty_file_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_upload(b"", "text/plain", "empty.txt", _ALLOWED, _MAX_SIZE)

    def test_mime_content_mismatch_raises(self):
        # Declare image/png but provide JPEG bytes
        with pytest.raises(ValidationError, match="content does not match"):
            validate_upload(_jpeg_bytes(), "image/png", "fake.png", _ALLOWED, _MAX_SIZE)

    def test_mime_with_charset_param_normalised(self):
        # "text/plain; charset=utf-8" should be treated as "text/plain"
        data = _text_bytes()
        fp = validate_upload(data, "text/plain; charset=utf-8", "file.txt", _ALLOWED, _MAX_SIZE)
        assert fp.size_bytes > 0

    def test_mime_case_insensitive(self):
        # Declared MIME is uppercase — should still be normalised
        fp = validate_upload(_jpeg_bytes(), "IMAGE/JPEG", "photo.jpg", _ALLOWED, _MAX_SIZE)
        assert fp.size_bytes > 0

    def test_returns_correct_fingerprint_for_known_data(self):
        data = b"%PDF-1.4 small"
        expected_sha = hashlib.sha256(data).hexdigest()
        fp = validate_upload(data, "application/pdf", "test.pdf", _ALLOWED, _MAX_SIZE)
        assert fp.sha256 == expected_sha


# ---------------------------------------------------------------------------
# verify_file_integrity
# ---------------------------------------------------------------------------

class TestVerifyFileIntegrity:
    def test_matching_hash_returns_true(self):
        data = b"test content"
        digest = hashlib.sha256(data).hexdigest()
        assert verify_file_integrity(data, digest) is True

    def test_tampered_data_returns_false(self):
        data = b"original"
        digest = hashlib.sha256(data).hexdigest()
        tampered = b"modified"
        assert verify_file_integrity(tampered, digest) is False

    def test_uppercase_stored_hash_accepted(self):
        data = b"case check"
        digest = hashlib.sha256(data).hexdigest().upper()
        assert verify_file_integrity(data, digest) is True

    def test_empty_data_against_empty_hash(self):
        digest = hashlib.sha256(b"").hexdigest()
        assert verify_file_integrity(b"", digest) is True

    def test_wrong_hash_length_returns_false(self):
        assert verify_file_integrity(b"data", "abc123") is False
