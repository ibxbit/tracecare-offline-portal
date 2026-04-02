"""
API tests for /api/cms — page CRUD, workflow transitions, revisions, sitemap.
"""
import uuid
import httpx
import pytest


def _page_payload(slug: str | None = None) -> dict:
    if slug is None:
        slug = f"test-page-{uuid.uuid4().hex[:8]}"
    return {
        "title": f"Test Page {slug}",
        "slug": slug,
        "content": "<p>Hello world</p>",
        "store_id": "default",
        "locale": "en",
        "is_in_sitemap": True,
        "sitemap_priority": 0.5,
        "sitemap_changefreq": "monthly",
    }


class TestCMSPageCRUD:
    def test_admin_can_create_page(self, client: httpx.Client, admin_headers: dict):
        payload = _page_payload()
        resp = client.post("/api/cms/pages", json=payload, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["slug"] == payload["slug"]
        assert body["status"] == "draft"
        client.delete(f"/api/cms/pages/{body['id']}", headers=admin_headers)

    def test_list_pages(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/cms/pages", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_page_by_id(self, client: httpx.Client, admin_headers: dict):
        page = client.post("/api/cms/pages", json=_page_payload(), headers=admin_headers).json()
        resp = client.get(f"/api/cms/pages/{page['id']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == page["id"]
        client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_get_page_by_slug(self, client: httpx.Client, admin_headers: dict):
        payload = _page_payload()
        page = client.post("/api/cms/pages", json=payload, headers=admin_headers).json()
        resp = client.get(f"/api/cms/pages/by-slug/{payload['slug']}", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["slug"] == payload["slug"]
        client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_duplicate_slug_same_store_rejected(self, client: httpx.Client, admin_headers: dict):
        payload = _page_payload()
        page = client.post("/api/cms/pages", json=payload, headers=admin_headers).json()
        resp = client.post("/api/cms/pages", json=payload, headers=admin_headers)
        assert resp.status_code == 409
        client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_update_page_content(self, client: httpx.Client, admin_headers: dict):
        page = client.post("/api/cms/pages", json=_page_payload(), headers=admin_headers).json()
        resp = client.put(f"/api/cms/pages/{page['id']}", json={
            "content": "<p>Updated content</p>",
            "change_note": "Updated body",
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["content"] == "<p>Updated content</p>"
        client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)


class TestCMSWorkflow:
    def _create_page(self, client, admin_headers) -> dict:
        return client.post("/api/cms/pages", json=_page_payload(), headers=admin_headers).json()

    def test_submit_for_review(self, client: httpx.Client, admin_headers: dict):
        page = self._create_page(client, admin_headers)
        resp = client.post(
            f"/api/cms/pages/{page['id']}/submit-review",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "review"
        client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_approve_moves_to_published(self, client: httpx.Client, admin_headers: dict):
        page = self._create_page(client, admin_headers)
        page_id = page["id"]
        client.post(f"/api/cms/pages/{page_id}/submit-review", headers=admin_headers)
        resp = client.post(f"/api/cms/pages/{page_id}/approve", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "published"
        client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)

    def test_reject_returns_to_draft(self, client: httpx.Client, admin_headers: dict):
        page = self._create_page(client, admin_headers)
        page_id = page["id"]
        client.post(f"/api/cms/pages/{page_id}/submit-review", headers=admin_headers)
        resp = client.post(f"/api/cms/pages/{page_id}/reject", json={
            "reason": "Needs revision"
        }, headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)

    def test_archive_published_page(self, client: httpx.Client, admin_headers: dict):
        page = self._create_page(client, admin_headers)
        page_id = page["id"]
        client.post(f"/api/cms/pages/{page_id}/submit-review", headers=admin_headers)
        client.post(f"/api/cms/pages/{page_id}/approve", headers=admin_headers)
        resp = client.post(f"/api/cms/pages/{page_id}/archive", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"
        client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)

    def test_restore_archived_page_to_draft(self, client: httpx.Client, admin_headers: dict):
        page = self._create_page(client, admin_headers)
        page_id = page["id"]
        client.post(f"/api/cms/pages/{page_id}/submit-review", headers=admin_headers)
        client.post(f"/api/cms/pages/{page_id}/approve", headers=admin_headers)
        client.post(f"/api/cms/pages/{page_id}/archive", headers=admin_headers)
        resp = client.post(f"/api/cms/pages/{page_id}/restore", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "draft"
        client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)

    def test_invalid_transition_rejected(self, client: httpx.Client, admin_headers: dict):
        """draft cannot be approved directly (must go through review first)."""
        page = self._create_page(client, admin_headers)
        resp = client.post(f"/api/cms/pages/{page['id']}/approve", headers=admin_headers)
        assert resp.status_code in (400, 409, 422)
        client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)


class TestCMSRevisions:
    def test_revisions_created_on_update(self, client: httpx.Client, admin_headers: dict):
        page = client.post("/api/cms/pages", json=_page_payload(), headers=admin_headers).json()
        page_id = page["id"]

        # Update creates a new revision
        client.put(f"/api/cms/pages/{page_id}", json={
            "content": "Revision 2 content",
            "change_note": "First edit",
        }, headers=admin_headers)

        resp = client.get(f"/api/cms/pages/{page_id}/revisions", headers=admin_headers)
        assert resp.status_code == 200
        revisions = resp.json()
        assert len(revisions) >= 1

        client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)

    def test_get_specific_revision(self, client: httpx.Client, admin_headers: dict):
        page = client.post("/api/cms/pages", json=_page_payload(), headers=admin_headers).json()
        page_id = page["id"]

        client.put(f"/api/cms/pages/{page_id}", json={
            "content": "Revision content",
            "change_note": "edit",
        }, headers=admin_headers)

        revisions = client.get(f"/api/cms/pages/{page_id}/revisions", headers=admin_headers).json()
        if revisions:
            rev_num = revisions[0]["revision_number"]
            resp = client.get(
                f"/api/cms/pages/{page_id}/revisions/{rev_num}", headers=admin_headers
            )
            assert resp.status_code == 200

        client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)


class TestCMSSitemap:
    def test_sitemap_json_returns_list(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/cms/sitemap.json", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_sitemap_xml_returns_xml(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/cms/sitemap.xml", headers=admin_headers)
        assert resp.status_code == 200
        content_type = resp.headers.get("content-type", "")
        assert "xml" in content_type or resp.text.startswith("<?xml")
