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

@pytest.fixture
def admin_tokens(client: httpx.Client) -> dict:
    """Function-scoped so every test gets a fresh admin session.

    The backend rotates `session_token_hash` on every login, which means any
    test that logs in as admin (e.g. refresh-rotation or last-login tests)
    would invalidate a session-scoped token for every subsequent test.
    """
    resp = client.post("/api/auth/login", json={
        "username": ADMIN_USERNAME,
        "password": ADMIN_PASSWORD,
    })
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()


@pytest.fixture
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


# ---------------------------------------------------------------------------
# Real-entity factories
# ---------------------------------------------------------------------------
#
# The application currently has no HTTP endpoint for placing an order, so
# exercising downstream flows (reviews, order-status notifications) would
# otherwise require skipping the most important leg of the journey. The
# tester container mounts the backend at /app and shares the production
# DATABASE_URL, so we import the real ORM models and persist real rows.
#
# This is NOT mocking. No review/notification/CMS code is stubbed — tests
# that use these fixtures exercise the genuine API endpoints against real
# DB rows that satisfy every FK and status invariant.


@pytest.fixture(scope="session")
def _backend_db():
    """Session-scoped SQLAlchemy session bound to the backend's real DB."""
    # Importing app.* requires the backend package to be importable.
    # In the tester container PYTHONPATH=/app (see docker-compose.yml).
    from app.database import SessionLocal  # type: ignore
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _make_order(
    db,
    customer_id: int,
    *,
    completed: bool = True,
    order_type: str = "product",
):
    """Persist a real Order row and (by default) mark it completed so reviews can be submitted."""
    from decimal import Decimal

    from app.models.order import Order, OrderStatus, OrderType  # type: ignore

    order = Order(
        order_number=f"TEST-{uuid.uuid4().hex[:12].upper()}",
        customer_id=customer_id,
        order_type=OrderType(order_type),
        status=OrderStatus.completed if completed else OrderStatus.pending,
        is_completed=completed,
        total_amount=Decimal("49.99"),
        notes="Created by API_tests fixture",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@pytest.fixture
def real_completed_order(_backend_db, temp_end_user: dict):
    """A real, completed Order owned by a real end_user — ready for review submission."""
    order = _make_order(_backend_db, customer_id=temp_end_user["id"], completed=True)
    yield order
    # Cleanup: clear reviews first (FK), then order
    from app.models.review import Review  # type: ignore
    _backend_db.query(Review).filter(Review.order_id == order.id).delete(synchronize_session=False)
    _backend_db.query(type(order)).filter_by(id=order.id).delete(synchronize_session=False)
    _backend_db.commit()


@pytest.fixture
def real_pending_order(_backend_db, temp_end_user: dict):
    """A real, still-pending Order — used to confirm the 'completed only' guard."""
    order = _make_order(_backend_db, customer_id=temp_end_user["id"], completed=False)
    yield order
    _backend_db.query(type(order)).filter_by(id=order.id).delete(synchronize_session=False)
    _backend_db.commit()
