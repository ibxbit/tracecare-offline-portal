"""
API tests for /api/products — CRUD, RBAC, duplicate-SKU guard, and trace events.
"""
import uuid
from datetime import datetime, timezone

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _product_payload(name: str | None = None, sku: str | None = None) -> dict:
    """Return a minimal valid product creation payload with unique defaults."""
    if name is None:
        name = f"Product {uuid.uuid4().hex[:8]}"
    if sku is None:
        sku = f"SKU-{uuid.uuid4().hex[:12].upper()}"
    return {
        "name": name,
        "sku": sku,
        "origin": "Test Origin",
        "batch_number": f"BATCH-{uuid.uuid4().hex[:6].upper()}",
    }


def _trace_event_payload(event_type: str = "harvested") -> dict:
    """Return a minimal valid trace-event creation payload."""
    return {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "location": "Warehouse A",
        "notes": "Automated test trace event",
    }


# ---------------------------------------------------------------------------
# CRUD lifecycle
# ---------------------------------------------------------------------------

class TestProductCRUD:
    """Happy-path create / list / get / update / delete cycle."""

    def test_admin_can_create_product(self, client: httpx.Client, admin_headers: dict):
        payload = _product_payload()
        resp = client.post("/api/products", json=payload, headers=admin_headers)
        assert resp.status_code == 201, f"Create failed: {resp.text}"
        body = resp.json()
        assert body["name"] == payload["name"]
        assert body["sku"] == payload["sku"]
        assert "id" in body
        assert "created_at" in body
        # Cleanup
        client.delete(f"/api/products/{body['id']}", headers=admin_headers)

    def test_catalog_manager_can_create_product(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_catalog_manager_headers: dict,
    ):
        payload = _product_payload()
        resp = client.post("/api/products", json=payload, headers=temp_catalog_manager_headers)
        assert resp.status_code == 201, f"Catalog manager create failed: {resp.text}"
        body = resp.json()
        assert body["sku"] == payload["sku"]
        # Cleanup (admin can always delete)
        client.delete(f"/api/products/{body['id']}", headers=admin_headers)

    def test_list_products_returns_list(self, client: httpx.Client, admin_headers: dict):
        resp = client.get("/api/products", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_product_by_id(self, client: httpx.Client, admin_headers: dict):
        payload = _product_payload()
        product = client.post("/api/products", json=payload, headers=admin_headers).json()
        try:
            resp = client.get(f"/api/products/{product['id']}", headers=admin_headers)
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == product["id"]
            assert body["name"] == payload["name"]
            assert body["sku"] == payload["sku"]
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_update_product(self, client: httpx.Client, admin_headers: dict):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.put(
                f"/api/products/{product['id']}",
                json={"name": "Updated Name", "origin": "Updated Origin"},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["name"] == "Updated Name"
            assert body["origin"] == "Updated Origin"
            # SKU must remain unchanged
            assert body["sku"] == product["sku"]
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_delete_product(self, client: httpx.Client, admin_headers: dict):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        resp = client.delete(f"/api/products/{product['id']}", headers=admin_headers)
        assert resp.status_code == 204
        # Confirm it is gone
        get_resp = client.get(f"/api/products/{product['id']}", headers=admin_headers)
        assert get_resp.status_code == 404

    def test_full_crud_lifecycle(self, client: httpx.Client, admin_headers: dict):
        """Create -> read -> update -> read -> delete -> confirm gone."""
        payload = _product_payload()

        # Create
        create_resp = client.post("/api/products", json=payload, headers=admin_headers)
        assert create_resp.status_code == 201
        product = create_resp.json()
        product_id = product["id"]

        try:
            # Read
            get_resp = client.get(f"/api/products/{product_id}", headers=admin_headers)
            assert get_resp.status_code == 200
            assert get_resp.json()["sku"] == payload["sku"]

            # Update
            update_resp = client.put(
                f"/api/products/{product_id}",
                json={"name": "Lifecycle Updated"},
                headers=admin_headers,
            )
            assert update_resp.status_code == 200
            assert update_resp.json()["name"] == "Lifecycle Updated"

            # Read again to confirm update
            get_resp2 = client.get(f"/api/products/{product_id}", headers=admin_headers)
            assert get_resp2.json()["name"] == "Lifecycle Updated"

            # Delete
            del_resp = client.delete(f"/api/products/{product_id}", headers=admin_headers)
            assert del_resp.status_code == 204

            # Confirm deleted
            gone_resp = client.get(f"/api/products/{product_id}", headers=admin_headers)
            assert gone_resp.status_code == 404
        except Exception:
            # Best-effort cleanup on failure
            client.delete(f"/api/products/{product_id}", headers=admin_headers)
            raise

    def test_created_product_appears_in_list(self, client: httpx.Client, admin_headers: dict):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.get("/api/products", headers=admin_headers)
            assert resp.status_code == 200
            ids = [p["id"] for p in resp.json()]
            assert product["id"] in ids
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# RBAC — role-based access control
# ---------------------------------------------------------------------------

class TestProductRBAC:
    """End users must not be able to create, update, or delete products."""

    def test_end_user_cannot_create_product(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.post(
            "/api/products", json=_product_payload(), headers=temp_end_user_headers
        )
        assert resp.status_code == 403

    def test_end_user_cannot_update_product(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.put(
                f"/api/products/{product['id']}",
                json={"name": "Hacked Name"},
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 403
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_end_user_cannot_delete_product(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.delete(
                f"/api/products/{product['id']}", headers=temp_end_user_headers
            )
            assert resp.status_code == 403
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_end_user_can_list_products(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/products", headers=temp_end_user_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_end_user_can_get_product(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.get(
                f"/api/products/{product['id']}", headers=temp_end_user_headers
            )
            assert resp.status_code == 200
            assert resp.json()["id"] == product["id"]
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_unauthenticated_cannot_list_products(self, client: httpx.Client):
        resp = client.get("/api/products")
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Validation — duplicate SKU, nonexistent product
# ---------------------------------------------------------------------------

class TestProductValidation:
    """Duplicate SKU -> 409, missing product -> 404."""

    def test_duplicate_sku_returns_409(self, client: httpx.Client, admin_headers: dict):
        payload = _product_payload()
        product = client.post("/api/products", json=payload, headers=admin_headers).json()
        try:
            # Same SKU, different name
            dup_payload = _product_payload(sku=payload["sku"])
            resp = client.post("/api/products", json=dup_payload, headers=admin_headers)
            assert resp.status_code == 409
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_get_nonexistent_product_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get("/api/products/999999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_nonexistent_product_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.put(
            "/api/products/999999999",
            json={"name": "Ghost"},
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_delete_nonexistent_product_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.delete("/api/products/999999999", headers=admin_headers)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Trace events — create and list
# ---------------------------------------------------------------------------

class TestTraceEvents:
    """POST and GET trace events on a product."""

    def test_admin_can_add_trace_event(self, client: httpx.Client, admin_headers: dict):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            payload = _trace_event_payload("harvested")
            resp = client.post(
                f"/api/products/{product['id']}/trace-events",
                json=payload,
                headers=admin_headers,
            )
            assert resp.status_code == 201, f"Add trace event failed: {resp.text}"
            body = resp.json()
            assert body["event_type"] == "harvested"
            assert body["product_id"] == product["id"]
            assert "id" in body
            assert "operator_id" in body
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_catalog_manager_can_add_trace_event(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_catalog_manager_headers: dict,
    ):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.post(
                f"/api/products/{product['id']}/trace-events",
                json=_trace_event_payload("processed"),
                headers=temp_catalog_manager_headers,
            )
            assert resp.status_code == 201
            assert resp.json()["event_type"] == "processed"
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_all_valid_event_types_accepted(
        self, client: httpx.Client, admin_headers: dict
    ):
        """Each enum value (harvested, processed, packaged, shipped, received) is valid."""
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            for event_type in ("harvested", "processed", "packaged", "shipped", "received"):
                resp = client.post(
                    f"/api/products/{product['id']}/trace-events",
                    json=_trace_event_payload(event_type),
                    headers=admin_headers,
                )
                assert resp.status_code == 201, (
                    f"event_type={event_type} should be accepted, got {resp.status_code}: {resp.text}"
                )
                assert resp.json()["event_type"] == event_type
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_list_trace_events(self, client: httpx.Client, admin_headers: dict):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            # Add two events
            client.post(
                f"/api/products/{product['id']}/trace-events",
                json=_trace_event_payload("harvested"),
                headers=admin_headers,
            )
            client.post(
                f"/api/products/{product['id']}/trace-events",
                json=_trace_event_payload("processed"),
                headers=admin_headers,
            )
            # List
            resp = client.get(
                f"/api/products/{product['id']}/trace-events",
                headers=admin_headers,
            )
            assert resp.status_code == 200
            events = resp.json()
            assert isinstance(events, list)
            assert len(events) >= 2
            event_types = [e["event_type"] for e in events]
            assert "harvested" in event_types
            assert "processed" in event_types
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)

    def test_end_user_can_list_trace_events(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            client.post(
                f"/api/products/{product['id']}/trace-events",
                json=_trace_event_payload("shipped"),
                headers=admin_headers,
            )
            resp = client.get(
                f"/api/products/{product['id']}/trace-events",
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 200
            assert isinstance(resp.json(), list)
            assert len(resp.json()) >= 1
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Trace events — RBAC
# ---------------------------------------------------------------------------

class TestTraceEventRBAC:
    """End users must not be able to add trace events."""

    def test_end_user_cannot_add_trace_event(
        self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict
    ):
        product = client.post(
            "/api/products", json=_product_payload(), headers=admin_headers
        ).json()
        try:
            resp = client.post(
                f"/api/products/{product['id']}/trace-events",
                json=_trace_event_payload("received"),
                headers=temp_end_user_headers,
            )
            assert resp.status_code == 403
        finally:
            client.delete(f"/api/products/{product['id']}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Trace events — 404 on missing product
# ---------------------------------------------------------------------------

class TestTraceEvent404:
    """Trace event endpoints must return 404 when the product does not exist."""

    def test_add_trace_event_nonexistent_product_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.post(
            "/api/products/999999999/trace-events",
            json=_trace_event_payload("harvested"),
            headers=admin_headers,
        )
        assert resp.status_code == 404

    def test_list_trace_events_nonexistent_product_returns_404(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = client.get(
            "/api/products/999999999/trace-events", headers=admin_headers
        )
        assert resp.status_code == 404
