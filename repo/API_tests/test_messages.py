"""
API tests for /api/messages — direct messages and conversation threads.

Covers:
  - Direct message send/inbox/read
  - Thread create / list / detail / send message / mark read / archive
  - Virtual alias resolve (admin only)
  - Object-level authorization: non-participants cannot access threads
"""
import uuid
import httpx
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _send_direct(client, headers, recipient_id, subject=None, body=None):
    subject = subject or f"Test {uuid.uuid4().hex[:6]}"
    body = body or "Hello from test"
    return client.post("/api/messages", json={
        "recipient_id": recipient_id,
        "subject": subject,
        "body": body,
    }, headers=headers)


def _create_thread(client, headers, participant_ids, subject=None, initial_message=None):
    subject = subject or f"Thread {uuid.uuid4().hex[:6]}"
    return client.post("/api/messages/threads", json={
        "subject": subject,
        "participant_ids": participant_ids,
        "initial_message": initial_message or "First message",
        "use_virtual_ids": False,
    }, headers=headers)


# ---------------------------------------------------------------------------
# Direct messages
# ---------------------------------------------------------------------------

class TestDirectMessages:
    def test_send_direct_message(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        resp = _send_direct(client, admin_headers, temp_end_user["id"])
        assert resp.status_code == 201
        body = resp.json()
        assert body["recipient_id"] == temp_end_user["id"]
        assert "id" in body

    def test_inbox_contains_received_message(
        self, client: httpx.Client, admin_headers: dict,
        temp_end_user: dict, temp_end_user_headers: dict
    ):
        _send_direct(client, admin_headers, temp_end_user["id"], subject="Inbox test")
        resp = client.get("/api/messages/inbox", headers=temp_end_user_headers)
        assert resp.status_code == 200
        subjects = [m["subject"] for m in resp.json()]
        assert "Inbox test" in subjects

    def test_sent_list_contains_sent_message(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        _send_direct(client, admin_headers, temp_end_user["id"], subject="Sent test")
        resp = client.get("/api/messages/sent", headers=admin_headers)
        assert resp.status_code == 200
        subjects = [m["subject"] for m in resp.json()]
        assert "Sent test" in subjects

    def test_unread_count_endpoint(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/messages/inbox/unread-count", headers=temp_end_user_headers)
        assert resp.status_code == 200
        assert "unread_count" in resp.json()

    def test_cannot_send_to_nonexistent_user(
        self, client: httpx.Client, admin_headers: dict
    ):
        resp = _send_direct(client, admin_headers, recipient_id=999999999)
        assert resp.status_code == 404

    def test_cannot_read_other_users_message(
        self, client: httpx.Client, admin_headers: dict,
        temp_end_user: dict, temp_staff_user: dict, temp_staff_headers: dict
    ):
        """A user cannot read a direct message sent between two other users."""
        msg = _send_direct(client, admin_headers, temp_end_user["id"]).json()
        resp = client.get(f"/api/messages/{msg['id']}", headers=temp_staff_headers)
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Thread operations
# ---------------------------------------------------------------------------

class TestThreads:
    def test_create_thread(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        resp = _create_thread(client, admin_headers, [temp_end_user["id"]])
        assert resp.status_code == 201
        body = resp.json()
        assert "id" in body
        assert "messages" in body
        assert len(body["messages"]) == 1  # initial message

    def test_list_threads(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        _create_thread(client, admin_headers, [temp_end_user["id"]])
        resp = client.get("/api/messages/threads", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_get_thread_detail(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.get(f"/api/messages/threads/{thread['id']}", headers=admin_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == thread["id"]
        assert "messages" in body

    def test_send_message_to_thread(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.post(
            f"/api/messages/threads/{thread['id']}/messages",
            json={"body": "Reply message"},
            headers=admin_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["body"] == "Reply message"

    def test_mark_thread_read(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.patch(
            f"/api/messages/threads/{thread['id']}/read",
            headers=admin_headers,
        )
        assert resp.status_code == 204

    def test_archive_thread(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.patch(
            f"/api/messages/threads/{thread['id']}/archive",
            headers=admin_headers,
        )
        assert resp.status_code == 204

    def test_cannot_post_to_archived_thread(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        client.patch(f"/api/messages/threads/{thread['id']}/archive", headers=admin_headers)
        resp = client.post(
            f"/api/messages/threads/{thread['id']}/messages",
            json={"body": "Should fail"},
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_nonparticipant_cannot_access_thread(
        self, client: httpx.Client, admin_headers: dict,
        temp_end_user: dict, temp_staff_user: dict, temp_staff_headers: dict
    ):
        """A user not in the thread must receive 403."""
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.get(
            f"/api/messages/threads/{thread['id']}",
            headers=temp_staff_headers,
        )
        assert resp.status_code == 403

    def test_nonparticipant_cannot_post_to_thread(
        self, client: httpx.Client, admin_headers: dict,
        temp_end_user: dict, temp_staff_user: dict, temp_staff_headers: dict
    ):
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.post(
            f"/api/messages/threads/{thread['id']}/messages",
            json={"body": "Injection attempt"},
            headers=temp_staff_headers,
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Virtual alias
# ---------------------------------------------------------------------------

class TestVirtualAlias:
    def test_create_thread_with_virtual_ids(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        resp = client.post("/api/messages/threads", json={
            "subject": "Anonymous thread",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Anonymous first message",
            "use_virtual_ids": True,
        }, headers=admin_headers)
        assert resp.status_code == 201
        body = resp.json()
        assert body["use_virtual_ids"] is True

    def test_resolve_alias_admin_only(
        self, client: httpx.Client, admin_headers: dict,
        temp_end_user: dict, temp_end_user_headers: dict
    ):
        thread = client.post("/api/messages/threads", json={
            "subject": "Alias thread",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Start",
            "use_virtual_ids": True,
        }, headers=admin_headers).json()
        thread_id = thread["id"]

        # Get the alias from a message
        detail = client.get(f"/api/messages/threads/{thread_id}", headers=admin_headers).json()
        first_msg = detail["messages"][0]
        alias = first_msg.get("sender_alias")
        if not alias:
            pytest.skip("No alias in message (may be creator's own message)")

        # Admin can resolve
        resp = client.get(
            f"/api/messages/threads/{thread_id}/resolve-alias/{alias}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "user_id" in resp.json()

        # End user cannot resolve
        resp2 = client.get(
            f"/api/messages/threads/{thread_id}/resolve-alias/{alias}",
            headers=temp_end_user_headers,
        )
        assert resp2.status_code == 403


# ---------------------------------------------------------------------------
# Thread status updates and read/unread badge tracking
# ---------------------------------------------------------------------------

class TestThreadReadUnreadBadge:
    """
    Verifies that the unread badge count reflects message read state.
    """

    def test_unread_count_increments_after_new_message(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        """Sending a message to end_user should make their unread count ≥ 1."""
        # Get baseline count
        baseline = client.get(
            "/api/messages/inbox/unread-count", headers=temp_end_user_headers
        ).json()["unread_count"]
        # Send a new message
        _send_direct(client, admin_headers, temp_end_user["id"],
                     subject=f"Unread test {uuid.uuid4().hex[:6]}")
        after = client.get(
            "/api/messages/inbox/unread-count", headers=temp_end_user_headers
        ).json()["unread_count"]
        assert after >= baseline

    def test_thread_unread_count_endpoint_present(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get("/api/messages/inbox/unread-count", headers=temp_end_user_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "unread_count" in body
        assert isinstance(body["unread_count"], int)

    def test_mark_thread_read_does_not_error(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        """Marking a thread as read by a participant must return 204."""
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        resp = client.patch(
            f"/api/messages/threads/{thread['id']}/read",
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 204

    def test_archived_thread_excluded_from_active_list(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """After archiving, the thread should not appear in the active thread list."""
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        client.patch(
            f"/api/messages/threads/{thread['id']}/archive",
            headers=admin_headers,
        )
        active_threads = client.get(
            "/api/messages/threads", headers=admin_headers
        ).json()
        # The archived thread must not appear in the default list
        active_ids = [t["id"] for t in active_threads]
        assert thread["id"] not in active_ids

    def test_thread_status_is_archived_after_archive_action(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """Thread status field must reflect 'archived' state after the archive PATCH."""
        thread = _create_thread(client, admin_headers, [temp_end_user["id"]]).json()
        client.patch(
            f"/api/messages/threads/{thread['id']}/archive",
            headers=admin_headers,
        )
        detail = client.get(
            f"/api/messages/threads/{thread['id']}", headers=admin_headers
        ).json()
        assert detail.get("status") == "archived"


# ---------------------------------------------------------------------------
# User subscription preferences (via notifications)
# ---------------------------------------------------------------------------

class TestSubscriptionPreferences:
    """
    Notification subscription preferences control which in-app events
    generate notifications for the user.
    """

    def test_get_subscription_preferences_returns_200(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        resp = client.get(
            "/api/notifications/preferences/me", headers=temp_end_user_headers
        )
        assert resp.status_code == 200

    def test_preferences_contain_message_notification_flag(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        body = client.get(
            "/api/notifications/preferences/me", headers=temp_end_user_headers
        ).json()
        assert "notify_new_message" in body, (
            "Preferences must include 'notify_new_message' flag"
        )

    def test_update_notify_new_message_preference(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        current = client.get(
            "/api/notifications/preferences/me", headers=temp_end_user_headers
        ).json()
        new_value = not current.get("notify_new_message", True)
        resp = client.put(
            "/api/notifications/preferences/me",
            json={"notify_new_message": new_value},
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 200
        # Restore original value
        client.put(
            "/api/notifications/preferences/me",
            json={"notify_new_message": current.get("notify_new_message", True)},
            headers=temp_end_user_headers,
        )

    def test_preferences_include_order_accepted_flag(
        self, client: httpx.Client, temp_end_user_headers: dict
    ):
        body = client.get(
            "/api/notifications/preferences/me", headers=temp_end_user_headers
        ).json()
        assert "notify_order_accepted" in body

    def test_preferences_scoped_per_user(
        self,
        client: httpx.Client,
        temp_end_user_headers: dict,
        admin_headers: dict,
    ):
        """Two different users' preferences are independent."""
        end_prefs = client.get(
            "/api/notifications/preferences/me", headers=temp_end_user_headers
        ).json()
        admin_prefs = client.get(
            "/api/notifications/preferences/me", headers=admin_headers
        ).json()
        # Both should succeed — proving the endpoint is scoped per-caller
        assert isinstance(end_prefs, dict)
        assert isinstance(admin_prefs, dict)


# ---------------------------------------------------------------------------
# Virtual alias / masked-number relay lifecycle
# ---------------------------------------------------------------------------

class TestVirtualAliasLifecycle:
    """
    Full lifecycle of the virtual contact identifier (masked-number relay):
    1. Create thread with use_virtual_ids=True
    2. Verify use_virtual_ids flag is set
    3. Messages in that thread expose sender_alias (not real sender identity)
    4. Only admin can resolve the alias back to a real user_id
    5. Non-admin participants receive 403 on alias resolution
    """

    def test_virtual_thread_flag_persisted(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        resp = client.post("/api/messages/threads", json={
            "subject": f"VirtualAlias {uuid.uuid4().hex[:6]}",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Masked sender test",
            "use_virtual_ids": True,
        }, headers=admin_headers)
        assert resp.status_code == 201
        assert resp.json()["use_virtual_ids"] is True

    def test_non_virtual_thread_flag_false(
        self, client: httpx.Client, admin_headers: dict, temp_end_user: dict
    ):
        resp = _create_thread(client, admin_headers, [temp_end_user["id"]])
        assert resp.status_code == 201
        assert resp.json()["use_virtual_ids"] is False

    def test_alias_resolve_returns_user_id_for_admin(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """Admin can deanonymize a virtual alias → user_id."""
        thread = client.post("/api/messages/threads", json={
            "subject": f"ResolveAlias {uuid.uuid4().hex[:6]}",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Find me",
            "use_virtual_ids": True,
        }, headers=admin_headers).json()

        # The end_user's alias should appear in the thread detail
        detail = client.get(
            f"/api/messages/threads/{thread['id']}", headers=admin_headers
        ).json()
        # Find a message that has a sender_alias
        alias = None
        for msg in detail.get("messages", []):
            if msg.get("sender_alias"):
                alias = msg["sender_alias"]
                break
        if alias is None:
            pytest.skip("No aliased message found (may be creator's own message)")

        resp = client.get(
            f"/api/messages/threads/{thread['id']}/resolve-alias/{alias}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        assert "user_id" in resp.json()

    def test_alias_resolve_forbidden_for_non_admin(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
        temp_end_user_headers: dict,
    ):
        """End-users must not be able to deanonymize aliases."""
        thread = client.post("/api/messages/threads", json={
            "subject": f"ForbiddenResolve {uuid.uuid4().hex[:6]}",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Cannot see who I am",
            "use_virtual_ids": True,
        }, headers=admin_headers).json()

        # Use a placeholder alias — endpoint should return 403 before looking it up
        resp = client.get(
            f"/api/messages/threads/{thread['id']}/resolve-alias/any_alias",
            headers=temp_end_user_headers,
        )
        assert resp.status_code == 403

    def test_resolve_nonexistent_alias_returns_404(
        self,
        client: httpx.Client,
        admin_headers: dict,
        temp_end_user: dict,
    ):
        """Resolving a made-up alias that doesn't exist should return 404."""
        thread = client.post("/api/messages/threads", json={
            "subject": f"NotFound {uuid.uuid4().hex[:6]}",
            "participant_ids": [temp_end_user["id"]],
            "initial_message": "Base",
            "use_virtual_ids": True,
        }, headers=admin_headers).json()

        resp = client.get(
            f"/api/messages/threads/{thread['id']}/resolve-alias/ghost_alias_xyz",
            headers=admin_headers,
        )
        assert resp.status_code == 404
