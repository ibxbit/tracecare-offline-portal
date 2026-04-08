# TraceCare Offline Compliance Portal

A fully offline, on-premises compliance management system for healthcare providers.
All data stays on your local network — no cloud calls, no external dependencies.

---

## Quick Start (Docker — recommended)

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

## Local Development Setup (without Docker)

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 16 running locally

### 1. Database

```bash
# Create the database and user
psql -U postgres -c "CREATE USER tracecare WITH PASSWORD 'tracecare';"
psql -U postgres -c "CREATE DATABASE tracecare OWNER tracecare;"
```

### 2. Backend

```bash
cd backend

# Install dependencies
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env — at minimum update DATABASE_URL, SECRET_KEY, and ENCRYPTION_KEY

# Run database migrations
alembic upgrade head

# Seed the default admin user
python init_db.py

# Start the development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server (proxies /api/* to localhost:8000)
npm run dev
```

Open **http://localhost:5173** (Vite dev server).

### 4. Generate Secrets

```bash
# JWT signing key
python -c "import secrets; print(secrets.token_hex(32))"

# Fernet field-encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Paste the outputs into the corresponding `.env` fields (`SECRET_KEY` and `ENCRYPTION_KEY`).

---

## Offline Mode

TraceCare is designed for fully air-gapped, on-premises deployments.

- **No cloud calls** are made during normal operation — all data stays on your local network.
- Private-IP enforcement: the backend rejects requests from public IP addresses (HTTP 403). Allowed ranges: `127.0.0.0/8`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`.
- File uploads are validated by **magic-byte MIME sniffing** — no external validation service is used.
- The notification retry engine runs entirely in-process on the local server.

To ensure strict offline mode, set `OFFLINE_MODE=true` in your `.env`. See `backend/.env.example` for all available options.

---

## Database Migrations

Migrations are managed with **Alembic**. All migration files live in `backend/alembic/versions/`.

```bash
cd backend

# Apply all pending migrations
alembic upgrade head

# Roll back one step
alembic downgrade -1

# Show current migration state
alembic current

# Create a new migration (auto-generates from model changes)
alembic revision --autogenerate -m "describe your change"
```

Migrations run automatically inside Docker at container startup via `init_db.py`.

---

## Proxy Pool Configuration

The proxy pool enables outbound connections through registered proxy servers (useful for offline relay scenarios where traffic must route through a specific gateway).

Proxies are managed entirely via the **Admin API** — no static config files are needed.

```bash
# Add a proxy entry (admin token required)
TOKEN=<your-admin-token>

curl -s -X POST http://localhost:8000/api/admin/proxy-pool \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "10.0.1.5",
    "port": 8080,
    "protocol": "http",
    "label": "gateway-proxy-1",
    "is_active": true
  }' | python3 -m json.tool

# List all proxy entries
curl -s http://localhost:8000/api/admin/proxy-pool \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Run a TCP health check on a proxy
curl -s -X PATCH http://localhost:8000/api/admin/proxy-pool/1/health-check \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

Enable proxy pool routing by setting `PROXY_POOL_ENABLED=true` and `PROXY_POOL_ROTATION=round_robin` in your `.env`.

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
  - `test_rbac.py` — role-based access enforcement: all roles, object-level auth, function-level auth, privilege escalation, malformed tokens
  - `test_notifications.py` — list, mark-read, preferences, delivery metrics, retry state machine, metrics field alignment
  - `test_messages.py` — direct messages, threads, read/unread badge, virtual alias lifecycle, subscription preferences

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

All variables are documented in `backend/.env.example`. Key variables:

| Variable                          | Default                                     | Description                                  |
|-----------------------------------|---------------------------------------------|----------------------------------------------|
| `DATABASE_URL`                    | `postgresql://tracecare:tracecare@db/...`   | PostgreSQL connection string                 |
| `SECRET_KEY`                      | `change-me-32-char-secret-key-here-00`      | JWT signing key (**change in production**)   |
| `ENCRYPTION_KEY`                  | (base64 Fernet key)                         | Field-encryption key (**change in production**) |
| `ACCESS_TOKEN_EXPIRE_MINUTES`     | `15`                                        | JWT access token lifetime (minutes)          |
| `REFRESH_TOKEN_EXPIRE_HOURS`      | `12`                                        | Refresh token lifetime (hours)               |
| `ATTACHMENTS_DIR`                 | `./uploads/catalog`                         | Catalog file upload path                     |
| `REVIEW_IMAGES_DIR`               | `./uploads/reviews`                         | Review image upload path                     |
| `PROXY_POOL_ENABLED`              | `false`                                     | Enable outbound proxy pool routing           |
| `PROXY_POOL_ROTATION`             | `round_robin`                               | Proxy selection strategy                     |
| `OFFLINE_MODE`                    | `true`                                      | Disable any optional outbound network calls  |
| `NOTIFICATION_RETRY_SCHEDULE_MINUTES` | `1,5,15`                              | Retry delays for failed notification delivery|
| `MAX_LOGIN_ATTEMPTS`              | `5`                                         | Failed login attempts before lockout         |
| `LOGIN_LOCKOUT_MINUTES`           | `15`                                        | Lockout duration after too many failures     |

See `backend/.env.example` for the full list with comments.

---

## Advanced Flows

### Masked-Number Relay / Virtual Contact Identifiers

Create a thread with `use_virtual_ids: true` to hide real participant identities. Each participant is assigned a random alias. Messages in that thread show `sender_alias` instead of real sender info.

Only admin can resolve an alias back to a real `user_id`:

```bash
# Create a virtual thread
curl -s -X POST http://localhost:8000/api/messages/threads \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"subject":"Anonymous inquiry","participant_ids":[2],"initial_message":"Hi","use_virtual_ids":true}'

# Resolve alias → real user (admin only)
curl -s http://localhost:8000/api/messages/threads/1/resolve-alias/ALIAS_VALUE \
  -H "Authorization: Bearer $TOKEN"
```

End-users and staff receive HTTP 403 on alias resolution — they can communicate without either party knowing the other's identity.

### Notification Retry Engine

Notifications that fail local delivery are retried on a backoff schedule:

| Attempt | Delay   |
|---------|---------|
| 1       | +1 min  |
| 2       | +5 min  |
| 3       | +15 min |
| 4+      | marked `failed` |

The retry engine (`process_due_retries()`) is triggered on every `GET /api/notifications` call — no background job scheduler is required. Delivery metrics are available to admins at `GET /api/notifications/admin/metrics`.

### Review Subject Types

Reviews require specifying a `subject_type` and the matching identifier field:

| subject_type   | Required field  | Notes                          |
|----------------|-----------------|--------------------------------|
| `product`      | `subject_id`    | Numeric product ID             |
| `catalog_item` | `subject_id`    | Numeric catalog item ID        |
| `exam_type`    | `subject_text`  | Free-text exam type name       |

Reviews can only be submitted for **completed orders**. The backend enforces `order.status == completed` (422 otherwise). A 10-minute client-side cooldown is also tracked in `localStorage` to prevent spam.

---

## Manual Verification Checklist

The following areas involve time-based, environmental, or cross-user behaviour that automated tests cannot fully exercise. Verify these manually after deployment:

### Authentication & Sessions
- [ ] Login lockout activates after 5 failed attempts and releases after 15 minutes
- [ ] Refresh token rotation issues a new refresh token on each use (old token is invalidated)
- [ ] Logout (`POST /api/auth/logout`) invalidates the token immediately (confirmed by a follow-up `GET /api/users/me` returning 401)

### File Uploads
- [ ] Uploading a file with a fake MIME header (e.g. a `.exe` renamed to `.jpg`) is rejected by magic-byte sniffing
- [ ] Upload path directories (`ATTACHMENTS_DIR`, `REVIEW_IMAGES_DIR`) are created on first use with correct permissions
- [ ] WebP images are rejected for review images (PNG/JPG only)

### Notification Retry Timing
- [ ] A notification created with a simulated delivery failure transitions to `retrying` and is visible in the list
- [ ] After the retry delay elapses, `GET /api/notifications` advances the notification to `delivered` or `failed`
- [ ] Admin metrics (`GET /api/notifications/admin/metrics`) reflect the updated counts

### Proxy Pool Connectivity
- [ ] Adding a reachable proxy via `POST /api/admin/proxy-pool` and running the health check returns `reachable: true`
- [ ] Adding an unreachable proxy returns `reachable: false` without crashing the server
- [ ] `PROXY_POOL_ENABLED=true` in `.env` routes outbound connections through the pool

### Virtual Alias (Masked-Number Relay)
- [ ] Messages in a virtual thread show `sender_alias` instead of username when viewed by non-admin
- [ ] Admin can resolve any alias via `GET /messages/threads/{id}/resolve-alias/{alias}`
- [ ] End-user attempting alias resolution receives HTTP 403

### CMS Workflow
- [ ] Full workflow cycle: draft → submit-review → approve → archive → restore
- [ ] Reject action sends `note` key (not `reason`) — verified in network tab
- [ ] Rollback to a previous revision creates a new revision entry, not an overwrite

### RBAC Boundary
- [ ] `catalog_manager` can create/edit CMS pages but cannot access `/api/admin/rules`
- [ ] `clinic_staff` can manage packages and exams but cannot access admin export endpoints
- [ ] `end_user` cannot submit a review for an order belonging to another user

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
