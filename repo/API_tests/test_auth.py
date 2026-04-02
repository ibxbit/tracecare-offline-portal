"""
API tests for /api/auth — login, lockout, token refresh/rotation, logout.
"""
import uuid

import httpx
import pytest

from .conftest import BASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD, _create_user, _delete_user


class TestLogin:
    def test_login_success_returns_tokens(self, client: httpx.Client):
        resp = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": ADMIN_PASSWORD,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body.get("token_type", "bearer").lower() == "bearer"

    def test_login_wrong_password_returns_401(self, client: httpx.Client):
        resp = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME,
            "password": "WrongPass!",
        })
        assert resp.status_code == 401

    def test_login_unknown_user_returns_401(self, client: httpx.Client):
        resp = client.post("/api/auth/login", json={
            "username": f"no_such_user_{uuid.uuid4().hex}",
            "password": "AnyPass@123!",
        })
        assert resp.status_code == 401

    def test_login_empty_credentials_returns_error(self, client: httpx.Client):
        resp = client.post("/api/auth/login", json={"username": "", "password": ""})
        assert resp.status_code in (401, 422)

    def test_login_sets_last_login(self, client: httpx.Client, admin_headers: dict):
        client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD
        })
        resp = client.get("/api/users/me", headers=admin_headers)
        assert resp.status_code == 200


class TestAccountLockout:
    def test_five_failures_lock_account(self, client: httpx.Client, admin_headers: dict):
        """A freshly-created user that receives 5 bad logins should be locked."""
        user = _create_user(client, admin_headers, role="end_user")
        uid = user["id"]

        try:
            for _ in range(5):
                client.post("/api/auth/login", json={
                    "username": user["username"],
                    "password": "WrongPass!",
                })
            # 6th attempt (or after 5) should return 429
            resp = client.post("/api/auth/login", json={
                "username": user["username"],
                "password": user["password"],  # correct pw — but locked
            })
            assert resp.status_code == 429
        finally:
            _delete_user(client, admin_headers, uid)

    def test_lockout_retry_after_header_present(self, client: httpx.Client, admin_headers: dict):
        user = _create_user(client, admin_headers, role="end_user")
        uid = user["id"]
        try:
            for _ in range(5):
                client.post("/api/auth/login", json={"username": user["username"], "password": "bad"})
            resp = client.post("/api/auth/login", json={"username": user["username"], "password": "bad"})
            assert resp.status_code == 429
            assert "Retry-After" in resp.headers
        finally:
            _delete_user(client, admin_headers, uid)


class TestTokenRefresh:
    def test_refresh_returns_new_tokens(self, client: httpx.Client, admin_headers: dict):
        tokens = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD
        }).json()
        resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 200
        new_tokens = resp.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

    def test_refresh_token_rotation(self, client: httpx.Client):
        """Old refresh token must be rejected after a single use."""
        tokens = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD
        }).json()
        old_refresh = tokens["refresh_token"]

        # Use the token once
        client.post("/api/auth/refresh", json={"refresh_token": old_refresh})

        # Attempt to reuse the old token
        resp = client.post("/api/auth/refresh", json={"refresh_token": old_refresh})
        assert resp.status_code == 401

    def test_invalid_refresh_token_returns_401(self, client: httpx.Client):
        resp = client.post("/api/auth/refresh", json={"refresh_token": "not.a.valid.token"})
        assert resp.status_code == 401

    def test_new_access_token_works(self, client: httpx.Client):
        tokens = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD
        }).json()
        new_tokens = client.post("/api/auth/refresh", json={
            "refresh_token": tokens["refresh_token"]
        }).json()
        resp = client.get("/api/users/me", headers={
            "Authorization": f"Bearer {new_tokens['access_token']}"
        })
        assert resp.status_code == 200


class TestLogout:
    def test_logout_invalidates_refresh_token(self, client: httpx.Client):
        tokens = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD
        }).json()
        # Logout
        resp = client.post("/api/auth/logout", json={
            "refresh_token": tokens["refresh_token"]
        }, headers={"Authorization": f"Bearer {tokens['access_token']}"})
        assert resp.status_code == 204

        # Refresh should now fail
        resp = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert resp.status_code == 401

    def test_logout_all_clears_session(self, client: httpx.Client, admin_headers: dict):
        tokens = client.post("/api/auth/login", json={
            "username": ADMIN_USERNAME, "password": ADMIN_PASSWORD
        }).json()
        access = tokens["access_token"]
        resp = client.post("/api/auth/logout-all",
                           headers={"Authorization": f"Bearer {access}"})
        assert resp.status_code == 204

        # Old refresh token should be invalid (session hash cleared)
        resp2 = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert resp2.status_code == 401
