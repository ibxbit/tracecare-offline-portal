"""
API tests for /api/exam-items — master dictionary of testable exam items.
Covers all 6 endpoints: create, list, get, update, deactivate, reactivate.
"""
import uuid
import httpx
import pytest


def _ei_payload(code=None, name=None):
    uid = uuid.uuid4().hex[:6].upper()
    return {
        "code": code or f"EI-{uid}",
        "name": name or f"Exam Item {uid}",
        "unit": "mg/dL",
        "ref_range_min": "10.0",
        "ref_range_max": "100.0",
        "applicable_sex": "all",
        "collection_method": "venipuncture",
    }


class TestExamItemCRUD:
    def test_admin_can_create(self, client: httpx.Client, admin_headers: dict):
        p = _ei_payload()
        r = client.post("/api/exam-items", json=p, headers=admin_headers)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["code"] == p["code"].upper()
        assert body["is_active"] is True
        # cleanup via deactivate (soft delete)
        client.delete(f"/api/exam-items/{body['id']}", headers=admin_headers)

    def test_list_returns_list(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/exam-items", headers=admin_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_get_by_id(self, client: httpx.Client, admin_headers: dict):
        p = _ei_payload()
        created = client.post("/api/exam-items", json=p, headers=admin_headers).json()
        try:
            r = client.get(f"/api/exam-items/{created['id']}", headers=admin_headers)
            assert r.status_code == 200
            assert r.json()["id"] == created["id"]
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)

    def test_get_nonexistent_returns_404(self, client: httpx.Client, admin_headers: dict):
        r = client.get("/api/exam-items/999999999", headers=admin_headers)
        assert r.status_code == 404

    def test_update_exam_item(self, client: httpx.Client, admin_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        try:
            r = client.put(f"/api/exam-items/{created['id']}", json={
                "name": "Updated Name",
                "unit": "g/L",
            }, headers=admin_headers)
            assert r.status_code == 200
            assert r.json()["name"] == "Updated Name"
            assert r.json()["unit"] == "g/L"
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)

    def test_update_empty_body_rejected(self, client: httpx.Client, admin_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        try:
            r = client.put(f"/api/exam-items/{created['id']}", json={}, headers=admin_headers)
            assert r.status_code == 422
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)


class TestExamItemDeactivateReactivate:
    def test_deactivate_sets_inactive(self, client: httpx.Client, admin_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        r = client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)
        assert r.status_code == 204
        # Verify inactive
        got = client.get(f"/api/exam-items/{created['id']}", headers=admin_headers)
        assert got.status_code == 200
        assert got.json()["is_active"] is False

    def test_deactivate_already_inactive_returns_409(self, client: httpx.Client, admin_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)
        r = client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)
        assert r.status_code == 409

    def test_reactivate(self, client: httpx.Client, admin_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)
        r = client.patch(f"/api/exam-items/{created['id']}/reactivate", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["is_active"] is True

    def test_reactivate_already_active_returns_409(self, client: httpx.Client, admin_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        try:
            r = client.patch(f"/api/exam-items/{created['id']}/reactivate", headers=admin_headers)
            assert r.status_code == 409
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)


class TestExamItemRBAC:
    def test_end_user_cannot_create(self, client: httpx.Client, temp_end_user_headers: dict):
        r = client.post("/api/exam-items", json=_ei_payload(), headers=temp_end_user_headers)
        assert r.status_code == 403

    def test_end_user_can_list(self, client: httpx.Client, temp_end_user_headers: dict):
        r = client.get("/api/exam-items", headers=temp_end_user_headers)
        assert r.status_code == 200

    def test_end_user_cannot_update(self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        try:
            r = client.put(f"/api/exam-items/{created['id']}", json={"name": "Hack"}, headers=temp_end_user_headers)
            assert r.status_code == 403
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)

    def test_end_user_cannot_deactivate(self, client: httpx.Client, admin_headers: dict, temp_end_user_headers: dict):
        created = client.post("/api/exam-items", json=_ei_payload(), headers=admin_headers).json()
        try:
            r = client.delete(f"/api/exam-items/{created['id']}", headers=temp_end_user_headers)
            assert r.status_code == 403
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)


class TestExamItemValidation:
    def test_duplicate_code_returns_409(self, client: httpx.Client, admin_headers: dict):
        p = _ei_payload()
        first = client.post("/api/exam-items", json=p, headers=admin_headers)
        assert first.status_code == 201
        try:
            dup = client.post("/api/exam-items", json=p, headers=admin_headers)
            assert dup.status_code == 409
        finally:
            client.delete(f"/api/exam-items/{first.json()['id']}", headers=admin_headers)

    def test_invalid_ref_range_rejected(self, client: httpx.Client, admin_headers: dict):
        p = _ei_payload()
        p["ref_range_min"] = "200.0"
        p["ref_range_max"] = "10.0"
        r = client.post("/api/exam-items", json=p, headers=admin_headers)
        assert r.status_code == 422

    def test_search_filter(self, client: httpx.Client, admin_headers: dict):
        p = _ei_payload()
        created = client.post("/api/exam-items", json=p, headers=admin_headers).json()
        try:
            r = client.get("/api/exam-items", params={"search": p["code"], "active_only": False}, headers=admin_headers)
            assert r.status_code == 200
            ids = [i["id"] for i in r.json()]
            assert created["id"] in ids
        finally:
            client.delete(f"/api/exam-items/{created['id']}", headers=admin_headers)
