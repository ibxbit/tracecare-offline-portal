"""
Explicit no-mock real-HTTP tests for POST /api/cms/pages/{page_id}/restore.

The existing suite touches restore inside a broader lifecycle; this file
isolates the endpoint and covers success + every failure / RBAC / state path.
"""
import uuid

import httpx
import pytest


def _new_slug() -> str:
    return f"restore-{uuid.uuid4().hex[:8]}"


def _archive_page(client: httpx.Client, page_id: int, headers: dict) -> None:
    # draft → review → published → archived
    client.post(f"/api/cms/pages/{page_id}/submit-review",
                json={"note": "r"}, headers=headers)
    client.post(f"/api/cms/pages/{page_id}/approve",
                json={"note": "a"}, headers=headers)
    client.post(f"/api/cms/pages/{page_id}/archive",
                json={"note": "x"}, headers=headers)


class TestCMSRestore:
    """POST /api/cms/pages/{page_id}/restore — move an archived page back to draft."""

    def test_restore_archived_page_returns_200_and_draft_status(
        self, client: httpx.Client, admin_headers: dict,
    ):
        page = client.post("/api/cms/pages", json={
            "title": "Restore happy path",
            "slug": _new_slug(),
            "content": "x",
        }, headers=admin_headers).json()
        try:
            _archive_page(client, page["id"], admin_headers)

            resp = client.post(
                f"/api/cms/pages/{page['id']}/restore",
                json={"note": "bring it back"},
                headers=admin_headers,
            )
            assert resp.status_code == 200, f"restore failed: {resp.text}"
            body = resp.json()
            assert body["id"] == page["id"]
            assert body["status"] == "draft", (
                "Restore must transition archived → draft per the workflow contract"
            )
            # A new revision entry is expected; current_revision should bump.
            assert body["current_revision"] >= 1
        finally:
            client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_restore_records_change_note_in_revision(
        self, client: httpx.Client, admin_headers: dict,
    ):
        """The optional `note` field on WorkflowTransitionRequest should be
        persisted into the revision history (observable via GET revisions)."""
        page = client.post("/api/cms/pages", json={
            "title": "Restore note test",
            "slug": _new_slug(),
            "content": "x",
        }, headers=admin_headers).json()
        try:
            _archive_page(client, page["id"], admin_headers)

            marker = f"restore-marker-{uuid.uuid4().hex[:6]}"
            resp = client.post(
                f"/api/cms/pages/{page['id']}/restore",
                json={"note": marker},
                headers=admin_headers,
            )
            assert resp.status_code == 200

            revs = client.get(
                f"/api/cms/pages/{page['id']}/revisions",
                headers=admin_headers,
            ).json()
            # At least one revision carries our marker in its change_note.
            assert any(r.get("change_note") == marker for r in revs), (
                f"Expected change_note '{marker}' in revisions; got: "
                f"{[r.get('change_note') for r in revs]}"
            )
        finally:
            client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_restore_on_draft_page_returns_409(
        self, client: httpx.Client, admin_headers: dict,
    ):
        """Only archived pages can be restored — other statuses yield 409."""
        page = client.post("/api/cms/pages", json={
            "title": "Restore conflict",
            "slug": _new_slug(),
            "content": "x",
        }, headers=admin_headers).json()
        try:
            resp = client.post(
                f"/api/cms/pages/{page['id']}/restore",
                json={"note": "should fail"},
                headers=admin_headers,
            )
            assert resp.status_code == 409
            detail = resp.json().get("detail", "").lower()
            assert "archived" in detail
        finally:
            client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_restore_on_published_page_returns_409(
        self, client: httpx.Client, admin_headers: dict,
    ):
        page = client.post("/api/cms/pages", json={
            "title": "Restore published conflict",
            "slug": _new_slug(),
            "content": "x",
        }, headers=admin_headers).json()
        try:
            client.post(f"/api/cms/pages/{page['id']}/submit-review",
                        json={"note": "r"}, headers=admin_headers)
            client.post(f"/api/cms/pages/{page['id']}/approve",
                        json={"note": "a"}, headers=admin_headers)

            resp = client.post(
                f"/api/cms/pages/{page['id']}/restore",
                json={"note": "no"},
                headers=admin_headers,
            )
            assert resp.status_code == 409
        finally:
            # Published pages can't be deleted — archive first
            client.post(f"/api/cms/pages/{page['id']}/archive",
                        json={"note": "cleanup"}, headers=admin_headers)
            client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_restore_nonexistent_page_returns_404(
        self, client: httpx.Client, admin_headers: dict,
    ):
        resp = client.post(
            "/api/cms/pages/999999999/restore",
            json={"note": "ghost"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_restore_requires_admin_role(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_catalog_manager_headers: dict,
    ):
        """restore is admin-only; catalog_manager must be 403 even though they
        can create/edit drafts."""
        page = client.post("/api/cms/pages", json={
            "title": "Restore RBAC",
            "slug": _new_slug(),
            "content": "x",
        }, headers=admin_headers).json()
        try:
            _archive_page(client, page["id"], admin_headers)

            resp = client.post(
                f"/api/cms/pages/{page['id']}/restore",
                json={"note": "not allowed"},
                headers=temp_catalog_manager_headers,
            )
            assert resp.status_code == 403

            # Verify archive state wasn't touched by the rejected call
            got = client.get(
                f"/api/cms/pages/{page['id']}", headers=admin_headers,
            ).json()
            assert got["status"] == "archived"
        finally:
            client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)

    def test_restore_then_edit_allowed(
        self, client: httpx.Client, admin_headers: dict,
    ):
        """After restore, the page is draft and editable again — archived
        pages previously refused edits with 409."""
        page = client.post("/api/cms/pages", json={
            "title": "Restore edit",
            "slug": _new_slug(),
            "content": "v1",
        }, headers=admin_headers).json()
        try:
            _archive_page(client, page["id"], admin_headers)
            # Edit while archived must fail
            blocked = client.put(
                f"/api/cms/pages/{page['id']}",
                json={"content": "blocked"},
                headers=admin_headers,
            )
            assert blocked.status_code == 409

            # Restore, then edit must succeed
            client.post(
                f"/api/cms/pages/{page['id']}/restore",
                json={"note": "r"},
                headers=admin_headers,
            )
            allowed = client.put(
                f"/api/cms/pages/{page['id']}",
                json={"content": "v2-after-restore"},
                headers=admin_headers,
            )
            assert allowed.status_code == 200
            assert allowed.json()["content"] == "v2-after-restore"
        finally:
            client.delete(f"/api/cms/pages/{page['id']}", headers=admin_headers)
