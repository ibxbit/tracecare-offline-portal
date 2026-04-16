# TraceCare Offline Compliance Portal

**Project type:** fullstack (FastAPI backend + Vue.js frontend + PostgreSQL)

A fully offline, on-premises compliance management system for healthcare providers.
All data stays on your local network — no cloud calls, no external dependencies.

---

## Startup

Run the full stack with one command:

```bash
docker-compose up
```

> The modern Docker CLI also accepts `docker compose up --build` — both variants start the same `docker-compose.yml` services.

That single command:
1. Starts **PostgreSQL 16** and runs all Alembic migrations automatically.
2. **Seeds the four demo users** (see the Demo Credentials table below).
3. Starts the **FastAPI backend** on the internal Docker network.
4. Builds and serves the **Vue.js frontend** through nginx on port **3000** (host).

**No local runtime installs are required.** You do not need Python, Node.js, npm, pip, psql, or a local PostgreSQL — everything runs inside Docker containers.

### Access

| What | URL |
|------|-----|
| Frontend (browser) | http://localhost:3000 |
| Backend API (via nginx proxy) | http://localhost:3000/api |
| API health check | http://localhost:3000/api/health |

The nginx frontend proxies all `/api/*` requests to the backend, so port 3000 is the only host port needed.

---

## Demo Credentials

All four users are seeded automatically by `init_db.py` on first startup. Each covers one of the RBAC roles exercised by the system.

| Role | Username | Password | Email |
|------|----------|----------|-------|
| `admin` | `admin` | `Admin@123!` | admin@example.com |
| `clinic_staff` | `staff` | `Staff@123!` | staff@example.com |
| `catalog_manager` | `catalog` | `Catalog@123!` | catalog@example.com |
| `end_user` | `patient` | `Patient@123!` | patient@example.com |

> Reset credentials by deleting the `pgdata` volume: `docker-compose down -v` then `docker-compose up` reseeds them.

---

## Verification

### 1. Confirm all services are up

```bash
docker-compose ps
```

All three services (`db`, `backend`, `frontend`) should show `running` or `healthy`.

### 2. Health check (curl)

```bash
curl http://localhost:3000/api/health
# {"status":"ok","service":"TraceCare Compliance Portal"}
```

### 3. Log in as each role via the API

```bash
# admin
curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123!"}'

# clinic_staff
curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"staff","password":"Staff@123!"}'

# catalog_manager
curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"catalog","password":"Catalog@123!"}'

# end_user
curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"patient","password":"Patient@123!"}'
```

Each login returns `access_token` and `refresh_token`.

### 4. Verify RBAC (admin endpoint)

```bash
TOKEN=$(curl -s -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"Admin@123!"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -s http://localhost:3000/api/users \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

### 5. UI verification flow

1. Open http://localhost:3000 in a browser.
2. Log in with `admin` / `Admin@123!`.
3. Navigate to the **Dashboard** — you should see the admin console greeting.
4. Navigate to **CMS** — create a draft page, submit for review, approve it.
5. Navigate to **Catalog** — create an item, upload a PDF attachment, verify the fingerprint.
6. Log out, log back in as `staff` / `Staff@123!` — confirm the Admin Console menu item is hidden.

### 6. Run the test suite (Docker-contained)

```bash
chmod +x run_tests.sh
./run_tests.sh
```

Expected output ends with `ALL TESTS PASSED`.

---

## Running Tests

```bash
./run_tests.sh              # run backend + frontend (all Docker)
./run_tests.sh backend      # backend only (unit + API tests)
./run_tests.sh frontend     # frontend only (vitest)
```

All test execution happens inside Docker containers — **no host-local toolchain (Python, Node, npm) is required**. Dependencies are baked into the test images at build time; no `npm install` or `pip install` runs at test-runtime.

The script starts the core services, waits for the backend healthcheck, then runs:

- **Backend** (`tester` service): `pytest unit_tests/ API_tests/` against the live backend + real DB
- **Frontend** (`frontend-tester` service): `vitest` inside jsdom with deps pre-installed

### Test inventory

- **`unit_tests/`** — pure-logic tests (no DB):
  `test_security.py`, `test_file_utils.py`, `test_rate_limiter.py`,
  `test_cms_workflow.py`, `test_review_credibility.py`

- **`API_tests/`** — real HTTP tests against the live backend (no mocks):
  `test_auth.py`, `test_packages.py`, `test_catalog.py`, `test_reviews.py`,
  `test_cms.py`, `test_admin.py`, `test_rbac.py`, `test_notifications.py`,
  `test_messages.py`, `test_e2e_flows.py`, `test_gaps_coverage.py`,
  `test_products.py`, `test_exams.py`, `test_exam_items.py`, `test_audit.py`,
  `test_endpoint_coverage.py`, `test_uncovered_endpoints.py`

- **`frontend/src/__tests__/`** — Vue component + Pinia store tests (real SFCs):
  `authStore.test.js`, `notificationsStore.test.js`, `routerGuards.test.js`,
  `loginView.test.js`, `dashboardView.test.js`, `authLogout.test.js`,
  `cmsWorkflow.test.js`, `navAndNotifications.test.js`, `packageSetup.test.js`,
  `reviewCooldown.test.js`, `router.test.js`

Tests are **idempotent** — safe to run repeatedly without resetting the database.
Each test uses unique names (UUIDs) and cleans up its own resources.

---

## Services

| Service | Image / Build | Port (host) | Description |
|---------|---------------|-------------|-------------|
| db | postgres:16 | (internal only) | PostgreSQL database (persistent volume) |
| backend | ./backend (Dockerfile) | (internal only) | FastAPI application + Alembic migrations |
| frontend | ./frontend (Dockerfile) | 3000 | Vue 3 SPA served by nginx (proxies /api to backend) |

---

## Security Notes

- The system enforces **private-IP-only** access (127.x, 10.x, 172.16-31.x, 192.168.x).
  External IPs receive HTTP 403.
- Passwords are hashed with **Argon2id** (no plain-text storage).
- All log output is filtered to redact tokens, passwords, and hashed values.
- The audit log records every authentication event and sensitive operation.
- File uploads are validated by **magic-byte sniffing** — declared MIME types are verified against file content.
- Findings fields in exams are **Fernet-encrypted at rest**.

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
│   ├── alembic/             Database migrations (001–012)
│   ├── init_db.py           Migration runner + demo user seeder
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                Vue 3 + Tailwind CSS SPA
│   ├── src/
│   │   ├── views/           Page components
│   │   ├── stores/          Pinia state stores
│   │   ├── router/          Vue Router configuration
│   │   └── __tests__/       Vitest component + store tests
│   ├── Dockerfile
│   ├── Dockerfile.test      Test image (deps baked at build time)
│   └── nginx.conf
├── unit_tests/              Pure-logic pytest tests
├── API_tests/               End-to-end HTTP tests (no mocks)
├── docker-compose.yml
├── run_tests.sh             Unified Docker-only test runner
└── README.md
```
