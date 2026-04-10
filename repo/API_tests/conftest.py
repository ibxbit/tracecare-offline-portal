"""
API test configuration.

All tests run against the live backend (http://backend:8000 inside Docker,
or API_BASE_URL env var for local runs).  The default admin user is seeded
by init_db.py when the backend starts.
"""
import os
import uuid

import httpx
import pytest

BASE_URL: str = os.environ.get("API_BASE_URL", "http://backend:8000")
ADMIN_USERNAME: str = "admin"
ADMIN_PASSWORD: str = "Admin@123!"


# ---------------------------------------------------------------------------
# Shared HTTP client (session-scoped — one connection pool for all tests)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def client() -> httpx.Client:
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as c:
        yield c


# ---------------------------------------------------------------------------
# Admin authentication
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def admin_tokens(client: httpx.Client) -> dict:
    resp = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope="session")
def admin_headers(admin_tokens: dict) -> dict:
    return {"Authorization": f"Bearer {admin_tokens['access_token']}"}


# ---------------------------------------------------------------------------
# Temporary user helpers
# ---------------------------------------------------------------------------

def _create_user(client: httpx.Client, admin_headers: dict, role: str = "end_user") -> dict:
    """Create a temporary user with a unique username and return its data."""
    uid = uuid.uuid4().hex[:10]
    username = f"tmp_{uid}"
    password = "TmpPass@2024!"
    email = f"{username}@example.com"
    resp = client.post("/api/users", json={
        "username": username,
        "email": email,
        "password": password,
        "role": role,
    }, headers=admin_headers)
    assert resp.status_code == 201, f"User creation failed: {resp.text}"
    data = resp.json()
    data["password"] = password  # attach plaintext for login fixtures
    return data


def _delete_user(client: httpx.Client, admin_headers: dict, user_id: int) -> None:
    client.delete(f"/api/users/{user_id}", headers=admin_headers)


# ---------------------------------------------------------------------------
# Per-test temporary user fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def temp_end_user(client: httpx.Client, admin_headers: dict) -> dict:
    user = _create_user(client, admin_headers, role="end_user")
    yield user
    _delete_user(client, admin_headers, user["id"])


@pytest.fixture
def temp_staff_user(client: httpx.Client, admin_headers: dict) -> dict:
    user = _create_user(client, admin_headers, role="clinic_staff")
    yield user
    _delete_user(client, admin_headers, user["id"])


@pytest.fixture
def temp_end_user_tokens(client: httpx.Client, temp_end_user: dict) -> dict:
    resp = client.post("/api/auth/login", json={
        "username": temp_end_user["username"],
        "password": temp_end_user["password"],
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def temp_end_user_headers(temp_end_user_tokens: dict) -> dict:
    return {"Authorization": f"Bearer {temp_end_user_tokens['access_token']}"}


@pytest.fixture
def temp_staff_tokens(client: httpx.Client, temp_staff_user: dict) -> dict:
    resp = client.post("/api/auth/login", json={
        "username": temp_staff_user["username"],
        "password": temp_staff_user["password"],
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def temp_staff_headers(temp_staff_tokens: dict) -> dict:
    return {"Authorization": f"Bearer {temp_staff_tokens['access_token']}"}


@pytest.fixture
def temp_catalog_manager(client: httpx.Client, admin_headers: dict) -> dict:
    user = _create_user(client, admin_headers, role="catalog_manager")
    yield user
    _delete_user(client, admin_headers, user["id"])


@pytest.fixture
def temp_catalog_manager_tokens(client: httpx.Client, temp_catalog_manager: dict) -> dict:
    resp = client.post("/api/auth/login", json={
        "username": temp_catalog_manager["username"],
        "password": temp_catalog_manager["password"],
    })
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def temp_catalog_manager_headers(temp_catalog_manager_tokens: dict) -> dict:
    return {"Authorization": f"Bearer {temp_catalog_manager_tokens['access_token']}"}
