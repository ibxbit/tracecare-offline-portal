# TraceCare Offline Compliance Portal

A fully offline, on-premises compliance management system for healthcare providers.
All data stays on your local network — no cloud calls, no external dependencies.

---

## Quick Start

```bash
docker compose up --build
```

That single command:
1. Starts PostgreSQL 16 and runs all Alembic migrations automatically.
2. Seeds the default **admin** user.
3. Starts the FastAPI backend on port 8000.
4. Builds and serves the Vue.js frontend through nginx on port 3000.

Open **http://localhost:3000** in your browser.

---

## Default Admin Credentials

| Field    | Value         |
|----------|---------------|
| Username | `admin`       |
| Password | `Admin@123!`  |

Change the password immediately after first login via **Profile → Change Password**.

---

## Services

| Service  | Image / Build         | Port (host) | Description                          |
|----------|-----------------------|-------------|--------------------------------------|
| db       | postgres:16           | 5432        | PostgreSQL database (persistent vol) |
| backend  | ./backend (Dockerfile)| 8000        | FastAPI application + Alembic        |
| frontend | ./frontend (Dockerfile)| 3000       | Vue 3 SPA served by nginx            |

The nginx frontend proxies all `/api/*` requests to the backend, so the
browser only needs to reach port 3000.

---

## API Health Check

```bash
curl http://localhost:8000/api/health
# {"status":"ok","service":"TraceCare Compliance Portal"}
```

---

## Running Tests

```bash
chmod +x run_tests.sh
./run_tests.sh
```

`run_tests.sh` starts the core services (if not already running), waits for the
backend healthcheck to pass, then executes all tests inside a dedicated
`tester` Docker container:

- **`unit_tests/`** — pure-logic tests (no DB required):
  - `test_security.py` — token revocation store, login lockout tracker, log redaction
  - `test_file_utils.py` — magic-byte MIME sniffing, SHA-256 fingerprinting, size limits
  - `test_rate_limiter.py` — sliding-window rate limiter
  - `test_cms_workflow.py` — CMS page status-machine transitions
  - `test_review_credibility.py` — credibility scoring formula

- **`API_tests/`** — end-to-end tests against the live backend:
  - `test_auth.py` — login, brute-force lockout, token refresh rotation, logout
  - `test_packages.py` — package CRUD, versioning, diff, activate/deactivate
  - `test_catalog.py` — catalog CRUD, file upload, integrity verification
  - `test_reviews.py` — review submission, moderation
  - `test_cms.py` — CMS workflow, revisions, sitemap
  - `test_admin.py` — site rules, tasks, API keys, system status, CSV exports
  - `test_rbac.py` — role-based access enforcement across all endpoints
  - `test_notifications.py` — list, mark-read, preferences, delivery metrics

Tests are **idempotent** — safe to run repeatedly without resetting the database.
Each test uses unique names (UUIDs) and cleans up its own resources.

---

## Verification Guide

### 1. Confirm all services are up

```bash
docker compose ps
```
All three services should show `running` or `healthy`.

### 2. Log in via the API

```bash
curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123!"}' | python3 -m json.tool
```
You should see `access_token` and `refresh_token` in the response.

### 3. Verify RBAC (admin endpoint)

```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:8000/api/users \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 4. Run the test suite

```bash
./run_tests.sh
```

Expected output ends with `ALL TESTS PASSED`.

---

## Environment Variables

The following variables are set in `docker-compose.yml` and can be overridden:

| Variable                     | Default                                    | Description                   |
|------------------------------|--------------------------------------------|-------------------------------|
| `DATABASE_URL`               | `postgresql://tracecare:tracecare@db/...`  | PostgreSQL connection string  |
| `SECRET_KEY`                 | `change-me-32-char-secret-key-here-00`     | JWT signing key (**change in production**) |
| `ENCRYPTION_KEY`             | (base64 Fernet key)                        | Field encryption key (**change in production**) |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| `15`                                       | JWT access token lifetime     |
| `REFRESH_TOKEN_EXPIRE_HOURS` | `12`                                       | Refresh token lifetime        |

---

## Security Notes

- The system enforces **private-IP-only** access (127.x, 10.x, 172.16-31.x, 192.168.x).
  External IPs receive HTTP 403.
- Passwords are hashed with **Argon2id** (no plain-text storage).
- All log output is filtered to redact tokens, passwords, and hashed values.
- The audit log records every authentication event and sensitive operation.
- File uploads are validated by **magic-byte sniffing** — declared MIME types are verified against file content.

---

## Project Layout

```
repo/
├── backend/                 FastAPI application
│   ├── app/
│   │   ├── core/            Security, auth, rate limiting, logging
│   │   ├── models/          SQLAlchemy ORM models
│   │   ├── routers/         API endpoint handlers
│   │   └── schemas/         Pydantic request/response schemas
│   ├── alembic/             Database migrations (001–009)
│   ├── init_db.py           Migration runner + admin user seeder
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                Vue 3 + Tailwind CSS SPA
│   ├── src/
│   │   ├── views/           Page components
│   │   ├── stores/          Pinia state stores
│   │   └── router/          Vue Router configuration
│   ├── Dockerfile
│   └── nginx.conf
├── unit_tests/              Pure-logic pytest tests
├── API_tests/               End-to-end HTTP tests
├── docker-compose.yml
├── run_tests.sh
└── README.md
```
