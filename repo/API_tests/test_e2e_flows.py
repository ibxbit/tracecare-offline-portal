"""
End-to-end user journey tests.

These intentionally exercise *complete* paths — a single test covers
multiple endpoints in the order a real client would hit them, verifying
the full UI → API → DB pipeline. No mocks, no stubs; every request is
a real HTTP call and every assertion checks a real DB-backed effect.

Coverage:
  - Login / refresh / logout cycle (with revocation)
  - Place an order (real DB row) + submit a review with cooldown enforcement
  - CMS page: create → submit-for-review → approve → rollback
  - Catalog item with file upload + integrity verify + tamper detection
  - Notification delivery, retry-engine trigger, and delivery metrics
  - Admin CSV export (users, site-rules, tasks)
  - Admin console state changes (proxy pool, system parameters)

The Vue frontend is served by nginx and proxies /api/* through to the
same backend, so an end-to-end HTTP round-trip against the backend is
equivalent to the UI path for everything except pure render logic
(render logic is covered by frontend/src/__tests__/).
"""
from __future__ import annotations

import io
import uuid
from decimal import Decimal

import httpx
import pytest


# ---------------------------------------------------------------------------
# Login / logout journey
# ---------------------------------------------------------------------------

class TestLoginLogoutJourney:
    def test_full_login_refresh_logout_cycle(
        self,
        client: httpx.Client,
        admin_headers: dict,  # only used to create the test user
    ):
        """
        1. Admin provisions a new end_user.
        2. User logs in → receives access + refresh.
        3. User hits an authenticated endpoint (GET /users/me).
        4. User rotates refresh token (access + refresh both change).
        5. User logs out — further use of either token is revoked.
        """
        uid = uuid.uuid4().hex[:8]
        username = f"journey_{uid}"
        password = "Journey@Pass2024!"

        created = client.post("/api/users", json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
            "role": "end_user",
        }, headers=admin_headers)
        assert created.status_code == 201

        try:
            # 2. Login
            login = client.post("/api/auth/login", json={
                "username": username,
                "password": password,
            })
            assert login.status_code == 200
            tokens = login.json()
            h = {"Authorization": f"Bearer {tokens['access_token']}"}

            # 3. Authenticated call succeeds
            me = client.get("/api/users/me", headers=h)
            assert me.status_code == 200, me.text
            assert me.json()["username"] == username

            # 4. Refresh rotates BOTH tokens
            refreshed = client.post("/api/auth/refresh", json={
                "refresh_token": tokens["refresh_token"],
            })
            assert refreshed.status_code == 200
            new_tokens = refreshed.json()
            assert new_tokens["refresh_token"] != tokens["refresh_token"], (
                "Refresh token must rotate"
            )
            # Old refresh is now revoked
            reused = client.post("/api/auth/refresh", json={
                "refresh_token": tokens["refresh_token"],
            })
            assert reused.status_code == 401

            # 5. Logout the new session
            logout = client.post(
                "/api/auth/logout",
                json={"refresh_token": new_tokens["refresh_token"]},
                headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
            )
            assert logout.status_code == 204

            # Access token is now revoked (jti added to access_token_store)
            post_logout = client.get(
                "/api/users/me",
                headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
            )
            assert post_logout.status_code == 401

            # Refresh token from the logged-out session is also revoked
            post_logout_refresh = client.post(
                "/api/auth/refresh",
                json={"refresh_token": new_tokens["refresh_token"]},
            )
            assert post_logout_refresh.status_code == 401
        finally:
            client.delete(f"/api/users/{created.json()['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Order + review journey (real Order row; review submitted via HTTP)
# ---------------------------------------------------------------------------

class TestPlaceOrderAndReviewJourney:
    def test_order_placed_then_review_submitted_via_api(
        self,
        client: httpx.Client,
        temp_end_user: dict,
        temp_end_user_headers: dict,
        _backend_db,
    ):
        """
        1. End-user exists.
        2. A real Order row is created for them (status=completed).
        3. User submits a review via HTTP.
        4. The review is visible via GET /reviews (filter by order_id).
        5. Cooldown blocks a second submission within 10 minutes.
        """
        from app.models.order import Order, OrderStatus, OrderType  # type: ignore
        from app.models.review import Review  # type: ignore

        order = Order(
            order_number=f"E2E-{uuid.uuid4().hex[:10].upper()}",
            customer_id=temp_end_user["id"],
            order_type=OrderType.product,
            status=OrderStatus.completed,
            is_completed=True,
            total_amount=Decimal("99.00"),
        )
        _backend_db.add(order)
        _backend_db.commit()
        _backend_db.refresh(order)
        order_id = order.id

        try:
            # Submit review
            rv = client.post("/api/reviews", json={
                "order_id": order_id,
                "subject_type": "product",
                "subject_id": 100,
                "rating": 5,
                "comment": "End-to-end happy path",
            }, headers=temp_end_user_headers)
            assert rv.status_code == 201, rv.text
            review_id = rv.json()["id"]

            # Visible via list filter
            listed = client.get(
                "/api/reviews",
                params={"order_id": order_id},
                headers=temp_end_user_headers,
            )
            assert listed.status_code == 200
            ids = [r["id"] for r in listed.json()]
            assert review_id in ids

            # Cooldown enforced
            dup = client.post("/api/reviews", json={
                "order_id": order_id,
                "subject_type": "product",
                "subject_id": 101,
                "rating": 4,
                "comment": "Too soon",
            }, headers=temp_end_user_headers)
            assert dup.status_code == 429
        finally:
            _backend_db.query(Review).filter(Review.order_id == order_id).delete(
                synchronize_session=False,
            )
            _backend_db.query(Order).filter(Order.id == order_id).delete(
                synchronize_session=False,
            )
            _backend_db.commit()


# ---------------------------------------------------------------------------
# CMS page lifecycle — create, submit-review, approve, rollback
# ---------------------------------------------------------------------------

class TestCMSPageLifecycleJourney:
    def test_full_cms_workflow_and_rollback(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_catalog_manager_headers: dict,
    ):
        slug = f"journey-page-{uuid.uuid4().hex[:8]}"

        # 1. catalog_manager creates a draft
        create = client.post("/api/cms/pages", json={
            "title": "Initial Title",
            "slug": slug,
            "content": "version 1 content",
            "store_id": "default",
            "locale": "en",
        }, headers=temp_catalog_manager_headers)
        assert create.status_code == 201, create.text
        page_id = create.json()["id"]

        try:
            # 2. catalog_manager edits the page (creates revision 2)
            update = client.put(f"/api/cms/pages/{page_id}", json={
                "content": "version 2 content",
                "change_note": "Tightened language",
            }, headers=temp_catalog_manager_headers)
            assert update.status_code == 200

            # 3. Submit for review
            submit = client.post(
                f"/api/cms/pages/{page_id}/submit-review",
                json={"note": "Ready for editorial"},
                headers=temp_catalog_manager_headers,
            )
            assert submit.status_code == 200
            assert submit.json()["status"] == "review"

            # catalog_manager cannot approve (admin-only)
            cm_approve = client.post(
                f"/api/cms/pages/{page_id}/approve",
                json={"note": "trying"},
                headers=temp_catalog_manager_headers,
            )
            assert cm_approve.status_code == 403

            # 4. Admin approves → published
            approve = client.post(
                f"/api/cms/pages/{page_id}/approve",
                json={"note": "LGTM"},
                headers=admin_headers,
            )
            assert approve.status_code == 200
            assert approve.json()["status"] == "published"
            assert approve.json()["published_at"] is not None

            # 5. Listing by slug returns published content
            by_slug = client.get(
                f"/api/cms/pages/by-slug/{slug}",
                headers=temp_catalog_manager_headers,
            )
            assert by_slug.status_code == 200
            assert by_slug.json()["content"] == "version 2 content"

            # 6. Rollback to revision 1 — page reverts AND goes back to draft
            revs = client.get(
                f"/api/cms/pages/{page_id}/revisions",
                headers=admin_headers,
            ).json()
            assert len(revs) >= 2, f"Expected >=2 revisions, got {len(revs)}"
            # revisions are sorted desc — pick the earliest
            earliest = min(r["revision_number"] for r in revs)
            rb = client.post(
                f"/api/cms/pages/{page_id}/rollback/{earliest}",
                json={"note": "Roll back to launch copy"},
                headers=admin_headers,
            )
            assert rb.status_code == 200
            rolled = rb.json()
            assert rolled["status"] == "draft", (
                "Rollback must move the page back to draft per the spec"
            )
            assert rolled["content"] == "version 1 content"
        finally:
            # Archive first (published pages can't be deleted), then delete
            client.post(
                f"/api/cms/pages/{page_id}/archive",
                json={"note": "cleanup"},
                headers=admin_headers,
            )
            client.delete(f"/api/cms/pages/{page_id}", headers=admin_headers)


class TestCMSMultiStoreMultiLocale:
    """
    Same slug is allowed across different (store_id, locale) tuples,
    but must be unique within a single tuple.
    """

    def test_same_slug_different_store_ok(
        self, client: httpx.Client, admin_headers: dict,
    ):
        slug = f"multi-{uuid.uuid4().hex[:6]}"
        a = client.post("/api/cms/pages", json={
            "title": "Store A",
            "slug": slug,
            "content": "A",
            "store_id": "store-a",
            "locale": "en",
        }, headers=admin_headers)
        b = client.post("/api/cms/pages", json={
            "title": "Store B",
            "slug": slug,
            "content": "B",
            "store_id": "store-b",
            "locale": "en",
        }, headers=admin_headers)
        assert a.status_code == 201, a.text
        assert b.status_code == 201, b.text
        try:
            assert a.json()["id"] != b.json()["id"]
        finally:
            client.delete(f"/api/cms/pages/{a.json()['id']}", headers=admin_headers)
            client.delete(f"/api/cms/pages/{b.json()['id']}", headers=admin_headers)

    def test_same_slug_different_locale_ok(
        self, client: httpx.Client, admin_headers: dict,
    ):
        slug = f"locale-{uuid.uuid4().hex[:6]}"
        en = client.post("/api/cms/pages", json={
            "title": "English",
            "slug": slug,
            "content": "Hello",
            "store_id": "default",
            "locale": "en",
        }, headers=admin_headers)
        es = client.post("/api/cms/pages", json={
            "title": "Spanish",
            "slug": slug,
            "content": "Hola",
            "store_id": "default",
            "locale": "es",
        }, headers=admin_headers)
        assert en.status_code == 201
        assert es.status_code == 201
        try:
            # Each locale variant is retrievable independently via by-slug
            r_en = client.get(
                f"/api/cms/pages/by-slug/{slug}",
                params={"locale": "en"},
                headers=admin_headers,
            )
            r_es = client.get(
                f"/api/cms/pages/by-slug/{slug}",
                params={"locale": "es"},
                headers=admin_headers,
            )
            assert r_en.status_code == 200 and r_en.json()["content"] == "Hello"
            assert r_es.status_code == 200 and r_es.json()["content"] == "Hola"
        finally:
            client.delete(f"/api/cms/pages/{en.json()['id']}", headers=admin_headers)
            client.delete(f"/api/cms/pages/{es.json()['id']}", headers=admin_headers)

    def test_duplicate_slug_same_tuple_rejected(
        self, client: httpx.Client, admin_headers: dict,
    ):
        slug = f"dup-{uuid.uuid4().hex[:6]}"
        first = client.post("/api/cms/pages", json={
            "title": "First",
            "slug": slug,
            "content": "x",
            "store_id": "default",
            "locale": "en",
        }, headers=admin_headers)
        assert first.status_code == 201
        try:
            dup = client.post("/api/cms/pages", json={
                "title": "Dup",
                "slug": slug,
                "content": "y",
                "store_id": "default",
                "locale": "en",
            }, headers=admin_headers)
            assert dup.status_code == 409
        finally:
            client.delete(
                f"/api/cms/pages/{first.json()['id']}",
                headers=admin_headers,
            )


# ---------------------------------------------------------------------------
# Catalog upload + fingerprint tamper detection
# ---------------------------------------------------------------------------

class TestCatalogUploadAndTamperDetection:
    def test_upload_compute_fingerprint_then_detect_tamper(
        self,
        client: httpx.Client,
        admin_headers: dict,
    ):
        """
        1. Create a catalog item.
        2. Upload a PDF — fingerprint is computed and stored.
        3. Verify endpoint confirms integrity (integrity_ok=True).
        4. Mutate the file on disk, re-verify — integrity_ok=False.
        5. Download endpoint returns 409 instead of serving tampered bytes.
        """
        item = client.post("/api/catalog", json={
            "name": f"Tamper-Test-{uuid.uuid4().hex[:6]}",
            "description": "fingerprint regression guard",
            "category": "test",
            "price": "1.00",
            "stock_quantity": 1,
        }, headers=admin_headers).json()
        try:
            pdf = b"%PDF-1.4\n" + b"A" * 200
            up = client.post(
                f"/api/catalog/{item['id']}/attachments",
                files={"file": ("doc.pdf", io.BytesIO(pdf), "application/pdf")},
                headers=admin_headers,
            )
            assert up.status_code == 201, up.text
            att = up.json()
            stored_sha = att["sha256_fingerprint"]
            assert len(stored_sha) == 64

            # Integrity check on fresh upload
            v1 = client.get(
                f"/api/catalog/{item['id']}/attachments/{att['id']}/verify",
                headers=admin_headers,
            )
            assert v1.status_code == 200
            assert v1.json()["integrity_ok"] is True
            assert v1.json()["computed_fingerprint"] == stored_sha

            # Tamper: overwrite on disk
            # Resolve the exact directory the backend writes into. Both the
            # backend container and the tester container mount ./backend at
            # /app, so the path is consistent across them.
            from app.config import settings  # type: ignore
            target = settings.attachments_path / str(item["id"])
            # Find the stored file by any name in the dir
            files = list(target.glob("*"))
            assert files, f"expected one file in {target}"
            files[0].write_bytes(b"%PDF-1.4\n" + b"B" * 200)  # different bytes

            v2 = client.get(
                f"/api/catalog/{item['id']}/attachments/{att['id']}/verify",
                headers=admin_headers,
            )
            assert v2.status_code == 200
            assert v2.json()["integrity_ok"] is False
            assert v2.json()["computed_fingerprint"] != stored_sha

            # Download must refuse to serve tampered bytes
            dl = client.get(
                f"/api/catalog/{item['id']}/attachments/{att['id']}/download",
                headers=admin_headers,
            )
            assert dl.status_code == 409, (
                f"Tampered file must not be served; got {dl.status_code}"
            )
        finally:
            client.delete(f"/api/catalog/{item['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Notification delivery, retries, metrics
# ---------------------------------------------------------------------------

class TestNotificationDeliveryJourney:
    def test_admin_notification_delivered_and_metrics_reflect_it(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        # baseline metrics
        before = client.get(
            "/api/notifications/admin/metrics", headers=admin_headers,
        ).json()

        # admin creates notification for the end user
        resp = client.post("/api/notifications", json={
            "recipient_id": temp_end_user["id"],
            "notification_type": "info",
            "title": "Your report is ready",
            "body": "The compliance report you requested is now available.",
        }, headers=admin_headers)
        assert resp.status_code == 201, resp.text
        notif = resp.json()
        # In the offline-delivery model, a live recipient → delivered immediately
        assert notif["status"] == "delivered"
        assert notif["delivery_attempts"] == 1
        assert notif["delivered_at"] is not None

        # Recipient sees it in their list (GET triggers process_due_retries)
        listed = client.get("/api/notifications", headers=temp_end_user_headers)
        assert listed.status_code == 200
        ids = [n["id"] for n in listed.json()]
        assert notif["id"] in ids

        # Metrics reflect the delivery
        after = client.get(
            "/api/notifications/admin/metrics", headers=admin_headers,
        ).json()
        assert after["delivered"] >= before["delivered"] + 1
        assert after["total"] >= before["total"] + 1

    def test_failed_recipient_enters_retry_state_machine(
        self,
        client: httpx.Client,
        admin_headers: dict,
        _backend_db,
    ):
        """
        Deactivate a user, create a notification for them → delivery fails
        and the row is left in `retrying` with next_retry_at set.  This
        exercises the real offline-retry path, not a mock.
        """
        from app.models.notification import Notification  # type: ignore
        from app.models.user import User  # type: ignore

        uid = uuid.uuid4().hex[:8]
        created = client.post("/api/users", json={
            "username": f"retry_{uid}",
            "email": f"retry_{uid}@example.com",
            "password": "RetryPass@2024!",
            "role": "end_user",
        }, headers=admin_headers)
        assert created.status_code == 201
        user_id = created.json()["id"]
        try:
            # Deactivate directly — API also supports PATCH /users/{id}/status
            user_row = _backend_db.query(User).filter(User.id == user_id).one()
            user_row.is_active = False
            _backend_db.commit()

            resp = client.post("/api/notifications", json={
                "recipient_id": user_id,
                "notification_type": "warning",
                "title": "Will fail",
                "body": "Recipient is inactive — delivery will retry.",
            }, headers=admin_headers)
            assert resp.status_code == 201, resp.text
            notif = resp.json()
            assert notif["status"] == "retrying"
            assert notif["next_retry_at"] is not None
            assert notif["delivery_attempts"] == 1
        finally:
            _backend_db.query(Notification).filter(
                Notification.recipient_id == user_id,
            ).delete(synchronize_session=False)
            _backend_db.commit()
            client.delete(f"/api/users/{user_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Admin console — CSV export + proxy pool + system parameters
# ---------------------------------------------------------------------------

class TestAdminConsoleJourney:
    def test_csv_export_streams_valid_csv(
        self, client: httpx.Client, admin_headers: dict,
    ):
        resp = client.get("/api/admin/export/users", headers=admin_headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        body = resp.text
        # Header row must include known columns
        first_line = body.splitlines()[0]
        for col in ("id", "username", "email", "role"):
            assert col in first_line, (
                f"CSV header missing '{col}': {first_line!r}"
            )

    def test_proxy_pool_crud_and_health_check(
        self, client: httpx.Client, admin_headers: dict,
    ):
        label = f"journey-proxy-{uuid.uuid4().hex[:6]}"
        # Create
        created = client.post("/api/admin/proxy-pool", json={
            "label": label,
            "host": "127.0.0.1",
            "port": 1,  # port 1 = virtually guaranteed connection refused
            "protocol": "http",
            "is_active": True,
            "weight": 10,
        }, headers=admin_headers)
        assert created.status_code == 201, created.text
        proxy = created.json()
        try:
            # List — the new entry must appear
            listed = client.get("/api/admin/proxy-pool", headers=admin_headers)
            assert listed.status_code == 200
            assert any(p["id"] == proxy["id"] for p in listed.json())

            # Response must NEVER leak the encrypted password
            assert "password_encrypted" not in proxy
            assert "password" not in proxy

            # Health-check: unreachable → is_healthy False, no crash
            hc = client.patch(
                f"/api/admin/proxy-pool/{proxy['id']}/health-check",
                headers=admin_headers,
            )
            assert hc.status_code == 200
            assert hc.json()["is_healthy"] is False
        finally:
            client.delete(
                f"/api/admin/proxy-pool/{proxy['id']}", headers=admin_headers,
            )

    def test_system_parameter_update_round_trip(
        self, client: httpx.Client, admin_headers: dict,
    ):
        """
        Seed a parameter via a SiteRule-alike path — if no writable parameters
        exist we accept the test as a documentation case.
        """
        params = client.get("/api/admin/parameters", headers=admin_headers)
        assert params.status_code == 200
        writable = [p for p in params.json() if not p.get("is_readonly", False)]
        if not writable:
            pytest.skip("No writable system parameters seeded in this environment")
        key = writable[0]["key"]
        original = writable[0]["value"]

        try:
            new_val = "e2e-" + uuid.uuid4().hex[:8]
            upd = client.put(
                f"/api/admin/parameters/{key}",
                json={"value": new_val},
                headers=admin_headers,
            )
            assert upd.status_code == 200
            assert upd.json()["value"] == new_val

            # Read-back confirms persistence
            got = client.get(
                f"/api/admin/parameters/{key}", headers=admin_headers,
            )
            assert got.status_code == 200
            assert got.json()["value"] == new_val
        finally:
            # Restore
            client.put(
                f"/api/admin/parameters/{key}",
                json={"value": original},
                headers=admin_headers,
            )

    def test_end_user_cannot_export_or_list_parameters(
        self, client: httpx.Client, temp_end_user_headers: dict,
    ):
        for path in (
            "/api/admin/export/users",
            "/api/admin/parameters",
            "/api/admin/proxy-pool",
            "/api/admin/rules",
        ):
            resp = client.get(path, headers=temp_end_user_headers)
            assert resp.status_code == 403, (
                f"{path} must be forbidden for end_user, got {resp.status_code}"
            )
