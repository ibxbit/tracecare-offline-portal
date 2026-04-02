"""
API tests for /api/catalog — catalog items, attachment upload, and integrity check.
"""
import io
import uuid
import httpx
import pytest


def _catalog_payload(title: str | None = None) -> dict:
    if title is None:
        title = f"Catalog Item {uuid.uuid4().hex[:8]}"
    return {
        "title": title,
        "description": "Test catalog item",
        "category": "test",
        "is_active": True,
    }


def _jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff" + b"\x00" * 20


def _pdf_bytes() -> bytes:
    return b"%PDF-1.4\n" + b"\x00" * 20


class TestCatalogCRUD:
    def test_admin_can_create_item(self, client: httpx.Client, admin_headers: dict):
        payload = _catalog_payload()
        resp = client.post("/api/catalog", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["title"] == payload["title"]
        client.delete(f"/api/catalog/{body['id']}", headers=admin_headers)

    def test_list_catalog_items(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/catalog", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_catalog_item_by_id(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/catalog/{item['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == item["id"]
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_get_nonexistent_item_returns_404(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/catalog/999999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_catalog_item(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        resp = client.put(f"/api/catalog/{item['id']}", json={
            "title": "Updated Title",
            "description": "Updated desc",
            "category": "updated",
            "is_active": True,
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated Title"
        client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)

    def test_delete_catalog_item(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        resp = client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)
        assert resp.status_code == 204
        # Confirm deleted
        assert client.get(f"/api/catalog/{item['id']}", headers=admin_headers).status_code == 404

    def test_end_user_cannot_create_item(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post("/api/catalog", json=_catalog_payload(), headers=temp_end_user_headers)
        assert resp.status_code == 403


class TestAttachmentUpload:
    def test_upload_pdf_attachment(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        resp = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        body = resp.json()
        assert "id" in body
        assert body.get("sha256_fingerprint") or body.get("sha256")

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_upload_image_attachment(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        resp = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("photo.jpg", io.BytesIO(_jpeg_bytes()), "image/jpeg")},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_upload_disallowed_type_rejected(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        resp = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("script.sh", io.BytesIO(b"#!/bin/bash\nrm -rf /"), "application/x-sh")},
            headers=admin_headers,
        )
        assert resp.status_code == 422

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)

    def test_attachment_listed_after_upload(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("doc.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        )
        resp = client.get(f"/api/catalog/{item_id}/attachments", headers=admin_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)


class TestFileIntegrity:
    def test_download_returns_file(self, client: httpx.Client, admin_headers: dict):
        item = client.post("/api/catalog", json=_catalog_payload(), headers=admin_headers).json()
        item_id = item["id"]

        attach = client.post(
            f"/api/catalog/{item_id}/attachments",
            files={"file": ("test.pdf", io.BytesIO(_pdf_bytes()), "application/pdf")},
            headers=admin_headers,
        ).json()
        attach_id = attach["id"]

        resp = client.get(
            f"/api/catalog/{item_id}/attachments/{attach_id}/download",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert len(resp.content) > 0

        client.delete(f"/api/catalog/{item_id}", headers=admin_headers)
