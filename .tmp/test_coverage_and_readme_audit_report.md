# Test Coverage Audit

## Project Type Detection
- Declared in README: **fullstack** (`repo/README.md:3`).

## Backend Endpoint Inventory
- Global API prefix: `/api` (`repo/backend/app/main.py:65-78`), plus `/api/health` (`repo/backend/app/main.py:81`).
- Router prefixes: `/auth`, `/users`, `/exam-items`, `/exams`, `/products`, `/packages`, `/catalog`, `/messages`, `/notifications`, `/cms`, `/reviews`, `/admin`, `/audit` (`repo/backend/app/routers/*.py`, `APIRouter(prefix=...)`).
- Total endpoints discovered statically: **152** (151 router handlers + 1 app handler).

### Endpoint Inventory (method + resolved path)
- `POST /api/auth/login`, `POST /api/auth/refresh`, `POST /api/auth/logout`, `POST /api/auth/logout-all` (`repo/backend/app/routers/auth.py:62,155,228,266`)
- `POST /api/users`, `GET /api/users`, `GET /api/users/me`, `GET /api/users/{user_id}`, `PUT /api/users/me`, `PUT /api/users/{user_id}`, `POST /api/users/me/change-password`, `DELETE /api/users/{user_id}` (`repo/backend/app/routers/users.py:20,50,61,66,78,95,119,149`)
- `POST /api/exam-items`, `GET /api/exam-items`, `GET /api/exam-items/{item_id}`, `PUT /api/exam-items/{item_id}`, `DELETE /api/exam-items/{item_id}`, `PATCH /api/exam-items/{item_id}/reactivate` (`repo/backend/app/routers/exam_items.py:41,81,108,118,166,187`)
- `POST /api/exams`, `GET /api/exams`, `GET /api/exams/{exam_id}`, `PUT /api/exams/{exam_id}`, `DELETE /api/exams/{exam_id}` (`repo/backend/app/routers/exams.py:96,128,152,164,207`)
- `POST /api/products`, `GET /api/products`, `GET /api/products/{product_id}`, `PUT /api/products/{product_id}`, `DELETE /api/products/{product_id}`, `POST /api/products/{product_id}/trace-events`, `GET /api/products/{product_id}/trace-events` (`repo/backend/app/routers/products.py:16,46,57,71,90,105,135`)
- `POST /api/packages`, `GET /api/packages`, `GET /api/packages/{package_id}`, `GET /api/packages/{package_id}/versions`, `POST /api/packages/{package_id}/new-version`, `GET /api/packages/{package_id}/diff/{other_id}`, `PATCH /api/packages/{package_id}/activate`, `PATCH /api/packages/{package_id}/deactivate`, `POST /api/packages/{package_id}/items`, `DELETE /api/packages/{package_id}/items/{exam_item_id}`, `DELETE /api/packages/{package_id}` (`repo/backend/app/routers/packages.py:244,290,313,323,343,417,455,491,516,565,624`)
- `POST /api/catalog`, `GET /api/catalog`, `GET /api/catalog/{item_id}`, `PUT /api/catalog/{item_id}`, `PATCH /api/catalog/{item_id}/deactivate`, `PATCH /api/catalog/{item_id}/reactivate`, `DELETE /api/catalog/{item_id}`, `PUT /api/catalog/{item_id}/stock`, `PUT /api/catalog/{item_id}/stock/set`, `POST /api/catalog/{item_id}/attachments`, `GET /api/catalog/{item_id}/attachments`, `GET /api/catalog/{item_id}/attachments/{att_id}/download`, `GET /api/catalog/{item_id}/attachments/{att_id}/verify`, `DELETE /api/catalog/{item_id}/attachments/{att_id}`, `GET /api/catalog/meta/allowed-mime-types` (`repo/backend/app/routers/catalog.py:123,155,298,308,331,351,368,400,428,448,515,531,586,634,662`)
- `POST /api/messages`, `GET /api/messages/inbox`, `GET /api/messages/sent`, `GET /api/messages/inbox/unread-count`, `GET /api/messages/{message_id}`, `PATCH /api/messages/{message_id}/read`, `DELETE /api/messages/{message_id}`, `POST /api/messages/threads`, `GET /api/messages/threads`, `GET /api/messages/threads/{thread_id}`, `POST /api/messages/threads/{thread_id}/messages`, `PATCH /api/messages/threads/{thread_id}/read`, `PATCH /api/messages/threads/{thread_id}/archive`, `GET /api/messages/threads/{thread_id}/my-alias`, `GET /api/messages/threads/{thread_id}/resolve-alias/{alias}` (`repo/backend/app/routers/messages.py:183,230,248,265,279,303,323,338,437,485,505,560,574,592,613`)
- `POST /api/notifications`, `POST /api/notifications/order-status`, `GET /api/notifications`, `GET /api/notifications/unread-count`, `GET /api/notifications/{notif_id}`, `PATCH /api/notifications/{notif_id}/read`, `POST /api/notifications/mark-read`, `POST /api/notifications/mark-all-read`, `DELETE /api/notifications/{notif_id}`, `GET /api/notifications/admin/metrics`, `GET /api/notifications/preferences/me`, `PUT /api/notifications/preferences/me` (`repo/backend/app/routers/notifications.py:96,121,179,210,226,235,251,272,291,307,323,335`)
- `POST /api/cms/pages`, `GET /api/cms/pages`, `GET /api/cms/pages/export`, `GET /api/cms/pages/{page_id}`, `GET /api/cms/pages/by-slug/{slug}`, `PUT /api/cms/pages/{page_id}`, `DELETE /api/cms/pages/{page_id}`, `POST /api/cms/pages/{page_id}/submit-review`, `POST /api/cms/pages/{page_id}/approve`, `POST /api/cms/pages/{page_id}/reject`, `POST /api/cms/pages/{page_id}/archive`, `POST /api/cms/pages/{page_id}/restore`, `GET /api/cms/pages/{page_id}/revisions`, `GET /api/cms/pages/{page_id}/revisions/{revision_number}`, `POST /api/cms/pages/{page_id}/rollback/{revision_number}`, `GET /api/cms/pages/{page_id}/preview`, `GET /api/cms/sitemap.json`, `GET /api/cms/sitemap.xml` (`repo/backend/app/routers/cms.py:111,145,184,239,252,277,314,334,354,379,401,418,442,457,478,537,551,580`)
- `POST /api/reviews`, `POST /api/reviews/{review_id}/followup`, `POST /api/reviews/{review_id}/images`, `GET /api/reviews/{review_id}/images/{image_id}/download`, `DELETE /api/reviews/{review_id}/images/{image_id}`, `GET /api/reviews`, `GET /api/reviews/summary`, `GET /api/reviews/{review_id}`, `PATCH /api/reviews/{review_id}/pin`, `PATCH /api/reviews/{review_id}/unpin`, `PATCH /api/reviews/{review_id}/collapse`, `PATCH /api/reviews/{review_id}/uncollapse`, `DELETE /api/reviews/{review_id}` (`repo/backend/app/routers/reviews.py:236,306,400,464,490,523,599,656,680,705,724,750,770`)
- `POST /api/admin/rules`, `GET /api/admin/rules`, `GET /api/admin/rules/{rule_id}`, `PUT /api/admin/rules/{rule_id}`, `PATCH /api/admin/rules/{rule_id}/toggle`, `DELETE /api/admin/rules/{rule_id}`, `GET /api/admin/parameters`, `GET /api/admin/parameters/{key}`, `PUT /api/admin/parameters/{key}`, `POST /api/admin/tasks`, `GET /api/admin/tasks`, `GET /api/admin/tasks/{task_id}`, `PATCH /api/admin/tasks/{task_id}/status`, `DELETE /api/admin/tasks/{task_id}`, `POST /api/admin/external/tasks`, `GET /api/admin/external/tasks/{task_id}`, `GET /api/admin/external/tasks`, `POST /api/admin/proxy-pool`, `GET /api/admin/proxy-pool`, `GET /api/admin/proxy-pool/{proxy_id}`, `PUT /api/admin/proxy-pool/{proxy_id}`, `DELETE /api/admin/proxy-pool/{proxy_id}`, `PATCH /api/admin/proxy-pool/{proxy_id}/health-check`, `POST /api/admin/api-keys`, `GET /api/admin/api-keys`, `GET /api/admin/api-keys/{key_id}`, `PUT /api/admin/api-keys/{key_id}`, `PATCH /api/admin/api-keys/{key_id}/rotate`, `PATCH /api/admin/api-keys/{key_id}/toggle`, `DELETE /api/admin/api-keys/{key_id}`, `GET /api/admin/export/site-rules`, `GET /api/admin/export/tasks`, `GET /api/admin/export/users`, `GET /api/admin/export/api-keys`, `GET /api/admin/system/status` (`repo/backend/app/routers/admin.py:163,189,208,220,241,257,274,287,301,331,352,381,393,425,448,473,496,524,552,573,587,612,627,669,695,715,727,747,776,791,825,852,891,918,949`)
- `GET /api/audit`, `GET /api/audit/{log_id}` (`repo/backend/app/routers/audit.py:40,77`)
- `GET /api/health` (`repo/backend/app/main.py:81`)

## API Test Mapping Table
| Endpoint scope | Covered | Test type | Test files | Evidence |
|---|---|---|---|---|
| All endpoint families listed above | yes | true no-mock HTTP (primary) | `API_tests/test_endpoint_coverage.py` + domain files (`test_auth.py`, `test_admin.py`, `test_catalog.py`, `test_cms.py`, `test_messages.py`, `test_notifications.py`, `test_packages.py`, `test_products.py`, `test_reviews.py`, `test_exams.py`, `test_exam_items.py`, `test_audit.py`, `test_uncovered_endpoints.py`, `test_cms_restore.py`) | Coverage-closure intent and router-organized endpoint tests are explicit (`repo/API_tests/test_endpoint_coverage.py:1-6`); restore endpoint has dedicated direct tests (`repo/API_tests/test_cms_restore.py:30-212`) |

## API Test Classification
- **True No-Mock HTTP:** predominant class in `API_tests/` (real `httpx.Client`, real `/api/*` requests, no transport/controller/service stubs) (`repo/API_tests/conftest.py:23-27`, `repo/API_tests/test_auth.py`, `repo/API_tests/test_admin.py`, `repo/API_tests/test_cms_restore.py`).
- **HTTP with Mocking:** none found in API test files by static inspection of patterns and direct reads.
- **Non-HTTP (unit/integration without HTTP):** backend logic-only tests are under `unit_tests/` (not `API_tests/`).
- **Mixed note:** `API_tests/conftest.py` includes `_backend_db` fixtures for real DB setup in some flows (`repo/API_tests/conftest.py:165-223`); this is direct DB fixture usage, not mocking.

## Mock Detection
- API tests: no explicit `vi.mock`, `jest.mock`, `sinon.stub`, `monkeypatch`, or `unittest.mock` markers found in inspected API files.
- Frontend tests do mock the API client boundary (expected for frontend unit tests): `vi.mock('../api/index.js', ...)` (`repo/frontend/src/__tests__/views.test.js:12`, `repo/frontend/src/__tests__/components.test.js:11`, `repo/frontend/src/__tests__/loginView.test.js:15`, `repo/frontend/src/__tests__/dashboardView.test.js:15`, `repo/frontend/src/__tests__/authStore.test.js:18`, `repo/frontend/src/__tests__/notificationsStore.test.js:8`, `repo/frontend/src/__tests__/routerGuards.test.js:18`).
- Unit tests use `MagicMock` in review credibility logic tests (`repo/unit_tests/test_review_credibility.py:11`).

## Coverage Summary
- Total endpoints: **152**.
- Endpoints with HTTP tests: **152** (static evidence indicates all endpoint families are exercised in API test suite, including prior gap `POST /api/cms/pages/{page_id}/restore`).
- Endpoints with TRUE no-mock HTTP tests: **152** (API suite-level classification).
- HTTP coverage %: **100%**.
- True API coverage %: **100%**.

## Unit Test Summary
### Backend Unit Tests
- Test files: `repo/unit_tests/test_security.py`, `repo/unit_tests/test_file_utils.py`, `repo/unit_tests/test_rate_limiter.py`, `repo/unit_tests/test_cms_workflow.py`, `repo/unit_tests/test_review_credibility.py`.
- Modules covered:
  - controllers: none as direct unit tests (covered mostly by API tests)
  - services/core: `app.core.token_store`, `app.core.log_filter`, `app.core.file_utils`, `app.core.rate_limiter`, `app.core.review_credibility`
  - repositories: no dedicated repository unit suite detected
  - auth/guards/middleware: token and lockout logic covered; middleware path itself not unit-tested directly
- Important backend modules not unit-tested directly: `app.core.security_middleware`, `app.core.dependencies`, `app.core.encryption`, `app.core.encrypted_type`, `app.core.notification_delivery`, repository/query layers.

### Frontend Unit Tests (STRICT REQUIREMENT)
- Frontend test files detected: `repo/frontend/src/__tests__/authStore.test.js`, `dashboardView.test.js`, `loginView.test.js`, `routerGuards.test.js`, `notificationsStore.test.js`, `cmsWorkflow.test.js`, `reviewCooldown.test.js`, `navAndNotifications.test.js`, `authLogout.test.js`, `packageSetup.test.js`, `router.test.js`, `views.test.js`, `components.test.js`.
- Framework/tools: Vitest + Vue Test Utils + Pinia + Vue Router test harness (`repo/frontend/vitest.config.js:1-11`, `repo/frontend/src/__tests__/views.test.js:7-10`, `repo/frontend/src/__tests__/components.test.js:6-10`).
- Actual frontend modules imported/rendered:
  - views: `LoginView`, `DashboardView`, `CMSView`, `CatalogView`, `ReviewsView`, `NotificationsView`, `PackagesView`
  - components: `NavBar`, `TraceTimeline`, `RoleGuard`, `StatusBadge`, `DataTable`, `Modal`
  - stores/router logic: `auth`, `notifications`, router guards
- Important frontend modules not directly tested (remaining): `MessagesView`, `PackageDiffView`, `ProductsView`, `PackageSetupView`, `AdminConsoleView`, `QuickViewsView`, `ProfileView`, `UsersView`, `ProductTraceView`, `ExamDetailView`, `ExamsView`.
- **Frontend unit tests: PRESENT**.

### Cross-Layer Observation
- Backend API coverage is now broad and deep.
- Frontend unit coverage materially improved (real SFC/component imports), but still not uniformly distributed across all views.

## API Observability Check
- Strong for API suite overall: tests show endpoint paths, request bodies/params, and response assertions (`repo/API_tests/test_cms_restore.py`, `repo/API_tests/test_uncovered_endpoints.py`, `repo/API_tests/test_endpoint_coverage.py`).
- Weak spots still exist in some status-only assertions (limited body semantics) in broad coverage tests.

## Tests Check
- Success/failure paths: present (e.g., restore success/409/403/404 in `repo/API_tests/test_cms_restore.py:30-212`).
- Edge/validation/RBAC: present across admin/packages/reviews/messages/catalog tests (`repo/API_tests/test_admin.py`, `repo/API_tests/test_uncovered_endpoints.py`, `repo/API_tests/test_messages.py`, `repo/API_tests/test_catalog.py`).
- Integration boundaries: HTTP layer is real in API tests via `httpx.Client(base_url=...)` (`repo/API_tests/conftest.py:23-27`).
- `run_tests.sh` check: Docker-based execution only (`repo/run_tests.sh:22,33,34,43`).
- Fullstack FE↔BE browser E2E: no dedicated Playwright/Cypress suite found by file-level inspection.

## Test Coverage Score (0–100)
- **95/100**

## Score Rationale
- Endpoint inventory appears fully exercised by API test suite after explicit restore endpoint addition.
- True no-mock HTTP discipline remains strong in API tests.
- Unit test base is solid for core backend utilities.
- Frontend unit tests are present and now include real views/components, but still not exhaustive across every major page.

## Key Gaps
- No explicit browser-level FE↔BE end-to-end automation suite (only API-level end-to-end and frontend unit tests).
- Remaining untested frontend views (direct-import basis) keep frontend depth below backend depth.

## Confidence & Assumptions
- Confidence: **medium-high**.
- Assumptions:
  - Coverage classification is static-only and based on visible endpoint declarations + visible HTTP calls in tests.
  - No runtime execution was performed.

## Test Coverage Verdict
- **PARTIAL PASS**

# README Audit

## Hard Gate Check Results
| Hard Gate | Result | Evidence |
|---|---|---|
| `repo/README.md` exists | PASS | `repo/README.md` |
| Clean/readable markdown structure | PASS | `repo/README.md:1-218` |
| Startup includes `docker-compose up` (backend/fullstack gate) | PASS | `repo/README.md:15` |
| Access method includes URL/port | PASS | `repo/README.md:32-35` |
| Verification method exists | PASS | `repo/README.md:55-117` |
| Environment rule: no runtime install/manual DB setup required | PASS | `repo/README.md:26`, `repo/README.md:137` |
| Demo credentials for auth roles | PASS | `repo/README.md:44-49` |

## High Priority Issues
- None (hard gates pass).

## Medium Priority Issues
- README verification example extracts token using host `python3` in shell pipeline (`repo/README.md:101-107`), which may confuse strictly Docker-only operators even though this is not an install step.

## Low Priority Issues
- Some verification examples are API-heavy; a shorter role-by-role UI checklist could improve operator usability.

## Hard Gate Failures
- None.

## README Verdict (PASS / PARTIAL PASS / FAIL)
- **PASS**
