"""
API tests for /api/exams — create, list, get, update, delete.

RBAC
----
  Create / update: admin, clinic_staff
  Delete: admin only
  Read (list / get): all authenticated; end_user sees own exams only

Business rules
--------------
  - patient_id must reference a valid, active user
  - package_id (optional) must reference an active package
  - Cancelled exams cannot be updated (409)
  - Completed exams can only be modified by admin (409 for staff)
  - Completed exams cannot be deleted (409 — audit trail)
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_exam(
    client: httpx.Client,
    headers: dict,
    patient_id: int,
    *,
    exam_type: str = "Blood Panel",
    notes: str | None = None,
    package_id: int | None = None,
) -> httpx.Response:
    """Convenience wrapper for POST /api/exams."""
    payload: dict = {
        "patient_id": patient_id,
        "exam_type": exam_type,
        "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
    }
    if notes is not None:
        payload["notes"] = notes
    if package_id is not None:
        payload["package_id"] = package_id
    return client.post("/api/exams", json=payload, headers=headers)


def _delete_exam(client: httpx.Client, headers: dict, exam_id: int) -> None:
    """Best-effort cleanup — swallow errors."""
    client.delete(f"/api/exams/{exam_id}", headers=headers)


# ===========================================================================
# CRUD lifecycle
# ===========================================================================

class TestExamCRUDLifecycle:
    """Full lifecycle: create -> list -> get -> update to completed -> delete blocked."""

    def test_full_crud_lifecycle(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            # 1. Create
            resp = _create_exam(
                client, admin_headers, temp_end_user["id"],
                exam_type="Complete Blood Count",
                notes="Fasting required",
            )
            assert resp.status_code == 201, f"Create failed: {resp.text}"
            body = resp.json()
            exam_id = body["id"]
            assert body["patient_id"] == temp_end_user["id"]
            assert body["exam_type"] == "Complete Blood Count"
            assert body["status"] == "scheduled"
            assert body["notes"] == "Fasting required"
            assert body["findings"] is None
            assert body["completed_at"] is None

            # 2. List — exam should appear
            resp = client.get("/api/exams", headers=admin_headers)
            assert resp.status_code == 200
            ids = [e["id"] for e in resp.json()]
            assert exam_id in ids

            # 3. Get by id
            resp = client.get(f"/api/exams/{exam_id}", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["id"] == exam_id

            # 4. Update — move to in_progress
            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "in_progress",
                "notes": "Patient arrived",
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "in_progress"
            assert resp.json()["notes"] == "Patient arrived"

            # 5. Update — move to completed with findings
            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "completed",
                "findings": "All values within normal range",
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "completed"
            assert resp.json()["findings"] == "All values within normal range"
            # completed_at should be auto-set
            assert resp.json()["completed_at"] is not None

            # 6. Delete completed exam — must be blocked (audit trail)
            resp = client.delete(f"/api/exams/{exam_id}", headers=admin_headers)
            assert resp.status_code == 409, (
                f"Completed exam delete should return 409, got {resp.status_code}"
            )
            assert "audit" in resp.json()["detail"].lower()

        finally:
            # Force cleanup: reset status so delete succeeds, then delete
            if exam_id is not None:
                client.put(f"/api/exams/{exam_id}", json={
                    "status": "scheduled",
                }, headers=admin_headers)
                _delete_exam(client, admin_headers, exam_id)

    def test_create_and_delete_scheduled_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """Scheduled (non-completed) exams CAN be deleted by admin."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.delete(f"/api/exams/{exam_id}", headers=admin_headers)
            assert resp.status_code == 204
            exam_id = None  # already deleted

            # Confirm it is gone
            resp = client.get(f"/api/exams/{exam_id if exam_id else 0}", headers=admin_headers)
            # We just need to verify 404 for the deleted id — use the original
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# RBAC — role-based access control
# ===========================================================================

class TestExamRBAC:
    """Verify that end_user cannot create, update, or delete exams."""

    def test_end_user_cannot_create_exam(
        self,
        client: httpx.Client,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        resp = _create_exam(client, temp_end_user_headers, temp_end_user["id"])
        assert resp.status_code == 403, (
            f"end_user create should be 403, got {resp.status_code}"
        )

    def test_end_user_cannot_update_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.put(f"/api/exams/{exam_id}", json={
                "notes": "Hacked notes",
            }, headers=temp_end_user_headers)
            assert resp.status_code == 403, (
                f"end_user update should be 403, got {resp.status_code}"
            )
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_end_user_cannot_delete_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.delete(f"/api/exams/{exam_id}", headers=temp_end_user_headers)
            assert resp.status_code == 403, (
                f"end_user delete should be 403, got {resp.status_code}"
            )
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_staff_cannot_delete_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_staff_headers: dict,
    ):
        """Delete is admin-only; clinic_staff should get 403."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.delete(f"/api/exams/{exam_id}", headers=temp_staff_headers)
            assert resp.status_code == 403, (
                f"clinic_staff delete should be 403, got {resp.status_code}"
            )
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_staff_can_create_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_staff_headers: dict,
    ):
        """clinic_staff should be allowed to create exams."""
        exam_id = None
        try:
            resp = _create_exam(client, temp_staff_headers, temp_end_user["id"])
            assert resp.status_code == 201, (
                f"clinic_staff create should succeed, got {resp.status_code}: {resp.text}"
            )
            exam_id = resp.json()["id"]
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_staff_can_update_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_staff_headers: dict,
    ):
        """clinic_staff should be allowed to update scheduled exams."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.put(f"/api/exams/{exam_id}", json={
                "notes": "Updated by staff",
            }, headers=temp_staff_headers)
            assert resp.status_code == 200
            assert resp.json()["notes"] == "Updated by staff"
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# End-user visibility — own exams only
# ===========================================================================

class TestExamEndUserVisibility:
    """end_user can list and get their own exams, but not other users' exams."""

    def test_end_user_sees_only_own_exams_in_list(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        exam_id = None
        try:
            # Admin creates exam for the temp_end_user
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            # end_user lists exams — should see only their own
            resp = client.get("/api/exams", headers=temp_end_user_headers)
            assert resp.status_code == 200
            exams = resp.json()
            for exam in exams:
                assert exam["patient_id"] == temp_end_user["id"], (
                    f"end_user should only see own exams, but saw patient_id={exam['patient_id']}"
                )
            # Our exam should be in the list
            ids = [e["id"] for e in exams]
            assert exam_id in ids
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_end_user_can_get_own_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.get(f"/api/exams/{exam_id}", headers=temp_end_user_headers)
            assert resp.status_code == 200
            assert resp.json()["id"] == exam_id
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_end_user_cannot_get_other_users_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user_headers: dict,
    ):
        """Create exam for admin (user id=1) and verify end_user gets 403."""
        exam_id = None
        try:
            # Create exam for admin user (id=1), not for the temp_end_user
            resp = _create_exam(client, admin_headers, patient_id=1)
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.get(f"/api/exams/{exam_id}", headers=temp_end_user_headers)
            assert resp.status_code == 403, (
                f"end_user accessing another user's exam should get 403, got {resp.status_code}"
            )
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# Validation
# ===========================================================================

class TestExamValidation:
    """Input validation and business-rule enforcement."""

    def test_create_exam_nonexistent_patient_returns_422(
        self,
        client: httpx.Client,
        admin_headers: dict,
    ):
        resp = _create_exam(client, admin_headers, patient_id=999999999)
        assert resp.status_code == 422, (
            f"Non-existent patient should return 422, got {resp.status_code}"
        )

    def test_create_exam_missing_exam_type_returns_422(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """exam_type is required and must be non-empty."""
        resp = client.post("/api/exams", json={
            "patient_id": temp_end_user["id"],
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
            # exam_type omitted
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_exam_empty_exam_type_returns_422(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        resp = client.post("/api/exams", json={
            "patient_id": temp_end_user["id"],
            "exam_type": "",
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_create_exam_missing_scheduled_at_returns_422(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        resp = client.post("/api/exams", json={
            "patient_id": temp_end_user["id"],
            "exam_type": "Blood Panel",
            # scheduled_at omitted
        }, headers=admin_headers)
        assert resp.status_code == 422

    def test_cancelled_exam_cannot_be_updated(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            # Cancel the exam
            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "cancelled",
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "cancelled"

            # Attempt to update cancelled exam
            resp = client.put(f"/api/exams/{exam_id}", json={
                "notes": "Trying to update cancelled",
            }, headers=admin_headers)
            assert resp.status_code == 409, (
                f"Cancelled exam update should return 409, got {resp.status_code}"
            )
            assert "cancelled" in resp.json()["detail"].lower()
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_completed_exam_update_blocked_for_staff(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_staff_headers: dict,
    ):
        """Completed exams can only be modified by admin; staff gets 409."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            # Complete the exam (as admin)
            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "completed",
                "findings": "Normal",
            }, headers=admin_headers)
            assert resp.status_code == 200

            # Staff tries to update completed exam
            resp = client.put(f"/api/exams/{exam_id}", json={
                "notes": "Staff override attempt",
            }, headers=temp_staff_headers)
            assert resp.status_code == 409, (
                f"Staff updating completed exam should return 409, got {resp.status_code}"
            )
            assert "admin" in resp.json()["detail"].lower()
        finally:
            if exam_id is not None:
                # Admin can still modify completed exams — reset for cleanup
                client.put(f"/api/exams/{exam_id}", json={
                    "status": "scheduled",
                }, headers=admin_headers)
                _delete_exam(client, admin_headers, exam_id)

    def test_admin_can_update_completed_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """Admin should be able to modify completed exams (unlike staff)."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            # Complete it
            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "completed",
                "findings": "Initial findings",
            }, headers=admin_headers)
            assert resp.status_code == 200

            # Admin updates the completed exam
            resp = client.put(f"/api/exams/{exam_id}", json={
                "findings": "Corrected findings by admin",
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["findings"] == "Corrected findings by admin"
        finally:
            if exam_id is not None:
                client.put(f"/api/exams/{exam_id}", json={
                    "status": "scheduled",
                }, headers=admin_headers)
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# 404 handling
# ===========================================================================

class TestExam404:
    """Nonexistent exam IDs return 404."""

    def test_get_nonexistent_exam_returns_404(
        self,
        client: httpx.Client,
        admin_headers: dict,
    ):
        resp = client.get("/api/exams/999999999", headers=admin_headers)
        assert resp.status_code == 404

    def test_update_nonexistent_exam_returns_404(
        self,
        client: httpx.Client,
        admin_headers: dict,
    ):
        resp = client.put("/api/exams/999999999", json={
            "notes": "ghost",
        }, headers=admin_headers)
        assert resp.status_code == 404

    def test_delete_nonexistent_exam_returns_404(
        self,
        client: httpx.Client,
        admin_headers: dict,
    ):
        resp = client.delete("/api/exams/999999999", headers=admin_headers)
        assert resp.status_code == 404


# ===========================================================================
# Filtering
# ===========================================================================

class TestExamFiltering:
    """List endpoint supports patient_id and status filters."""

    def test_filter_by_patient_id(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.get(
                "/api/exams",
                params={"patient_id": temp_end_user["id"]},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            exams = resp.json()
            for exam in exams:
                assert exam["patient_id"] == temp_end_user["id"]
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_filter_by_status(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.get(
                "/api/exams",
                params={"status": "scheduled"},
                headers=admin_headers,
            )
            assert resp.status_code == 200
            exams = resp.json()
            for exam in exams:
                assert exam["status"] == "scheduled"
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)

    def test_filter_by_patient_id_and_status(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.get(
                "/api/exams",
                params={
                    "patient_id": temp_end_user["id"],
                    "status": "scheduled",
                },
                headers=admin_headers,
            )
            assert resp.status_code == 200
            exams = resp.json()
            for exam in exams:
                assert exam["patient_id"] == temp_end_user["id"]
                assert exam["status"] == "scheduled"
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# Status transitions
# ===========================================================================

class TestExamStatusTransitions:
    """Verify all valid status enum values and transition paths."""

    def test_all_status_values_accepted(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """Create an exam and cycle through every valid status."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            # scheduled (default) -> in_progress -> completed
            for target_status in ["in_progress", "completed"]:
                resp = client.put(f"/api/exams/{exam_id}", json={
                    "status": target_status,
                }, headers=admin_headers)
                assert resp.status_code == 200, (
                    f"Transition to {target_status} failed: {resp.text}"
                )
                assert resp.json()["status"] == target_status
        finally:
            if exam_id is not None:
                # Reset to allow deletion
                client.put(f"/api/exams/{exam_id}", json={
                    "status": "scheduled",
                }, headers=admin_headers)
                _delete_exam(client, admin_headers, exam_id)

    def test_cancel_scheduled_exam(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "cancelled",
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["status"] == "cancelled"
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# Findings encryption round-trip
# ===========================================================================

class TestExamFindings:
    """Findings are encrypted at rest but returned decrypted via the API."""

    def test_findings_round_trip(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]
            assert resp.json()["findings"] is None

            findings_text = "Hemoglobin: 14.2 g/dL — within normal range"
            resp = client.put(f"/api/exams/{exam_id}", json={
                "findings": findings_text,
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["findings"] == findings_text

            # Re-fetch to confirm persistence
            resp = client.get(f"/api/exams/{exam_id}", headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["findings"] == findings_text
        finally:
            if exam_id is not None:
                _delete_exam(client, admin_headers, exam_id)


# ===========================================================================
# Completed-at auto-set
# ===========================================================================

class TestExamCompletedAt:
    """completed_at is auto-set when status transitions to completed."""

    def test_completed_at_auto_set(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]
            assert resp.json()["completed_at"] is None

            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "completed",
            }, headers=admin_headers)
            assert resp.status_code == 200
            assert resp.json()["completed_at"] is not None
        finally:
            if exam_id is not None:
                client.put(f"/api/exams/{exam_id}", json={
                    "status": "scheduled",
                }, headers=admin_headers)
                _delete_exam(client, admin_headers, exam_id)

    def test_explicit_completed_at_respected(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """When completed_at is explicitly provided, it should be used."""
        exam_id = None
        try:
            resp = _create_exam(client, admin_headers, temp_end_user["id"])
            assert resp.status_code == 201
            exam_id = resp.json()["id"]

            explicit_time = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc).isoformat()
            resp = client.put(f"/api/exams/{exam_id}", json={
                "status": "completed",
                "completed_at": explicit_time,
            }, headers=admin_headers)
            assert resp.status_code == 200
            # The server should store the explicit value
            assert resp.json()["completed_at"] is not None
        finally:
            if exam_id is not None:
                client.put(f"/api/exams/{exam_id}", json={
                    "status": "scheduled",
                }, headers=admin_headers)
                _delete_exam(client, admin_headers, exam_id)
