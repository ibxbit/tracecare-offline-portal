# TraceCare Offline Compliance Portal - Static Delivery Acceptance + Architecture Audit

## 1) Verdict

**Overall: Partial Pass (Not yet acceptable for final delivery).**

- Core architecture and most functional domains are implemented and wired (`backend/app/main.py:66`, `backend/app/main.py:78`).
- However, at least one **Blocker** and multiple **High** issues remain in security/configuration and delivery-test alignment (details in section 5).
- Because this is a **static-only** audit, runtime behavior claims are marked accordingly.

## 2) Scope / Boundary (Static-Only)

- Method: repository static review only; no app startup, no Docker, no test execution.
- Evidence sources: code, schemas, routers, config, docs, and test files.
- Exclusions:
  - Runtime correctness under real DB/network load.
  - Actual enforcement outcomes requiring live requests.
  - Performance and deployment hardening validation.
- Labels used:
  - **Cannot Confirm Statistically**
  - **Manual Verification Required**

## 3) Requirement Mapping (Prompt Acceptance Areas)

| Acceptance Section | Static Status | Evidence |
|---|---|---|
| 1. Exam Items + Packages (versioning/diff/activation) | **Partial Pass** | Versioned package create/new-version/diff/activate/deactivate present (`backend/app/routers/packages.py:343`, `backend/app/routers/packages.py:417`, `backend/app/routers/packages.py:455`, `backend/app/routers/packages.py:491`); role guards present (`backend/app/routers/packages.py:248`). Test/API drift exists (section 5). |
| 2. Catalog + Attachments (validation/fingerprint/download) | **Pass** | MIME/size validation and fingerprinting in upload flow (`backend/app/routers/catalog.py:479`, `backend/app/routers/catalog.py:506`); integrity verification endpoint (`backend/app/routers/catalog.py:587`, `backend/app/routers/catalog.py:617`); auth guards for write/read paths (`backend/app/routers/catalog.py:127`, `backend/app/routers/catalog.py:519`). |
| 3. Reviews + Moderation + Follow-up | **Partial Pass** | Review/follow-up/image/moderation endpoints exist (`backend/app/routers/reviews.py:299`, `backend/app/routers/reviews.py:394`, `backend/app/routers/reviews.py:673`); RBAC/object checks present (`backend/app/routers/reviews.py:536`, `backend/app/routers/reviews.py:678`). Frontend filter contract drift exists (`frontend/src/views/ReviewsView.vue:406`, `backend/app/routers/reviews.py:517`). |
| 4. CMS Workflow + Revisions + Rollback + Sitemap | **Partial Pass** | Draft/review/publish/archive flow and rollback implemented (`backend/app/routers/cms.py:334`, `backend/app/routers/cms.py:359`, `backend/app/routers/cms.py:478`); revision history present (`backend/app/routers/cms.py:442`). Sitemap endpoints have no auth dependency and may be intentionally public (`backend/app/routers/cms.py:551`, `backend/app/routers/cms.py:580`) - verify expectation. |
| 5. Messages/Threads + Virtual Alias Relay | **Pass** | Virtual alias design and thread flow implemented (`backend/app/routers/messages.py:12`, `backend/app/routers/messages.py:338`); participant-level authorization helper present (`backend/app/routers/messages.py:98`). |
| 6. Notifications + Admin/API-Key + Metrics | **Partial Pass** | Notification APIs, retry processing trigger, preferences, and admin metrics exist (`backend/app/routers/notifications.py:179`, `backend/app/routers/notifications.py:194`, `backend/app/routers/notifications.py:307`); API-key auth + IP allowlist + per-key rate limit for external admin endpoints (`backend/app/routers/admin.py:106`, `backend/app/routers/admin.py:131`, `backend/app/routers/admin.py:141`). Retry schedule configurability does not match docs (section 5). |

## 4) Section-by-Section Review

### 4.1 Exam Items + Packages

- Package lifecycle is clearly versioned and immutable-by-copy (`backend/app/routers/packages.py:343`, `backend/app/routers/packages.py:355`).
- Diff endpoint exists and enforces same-package semantics (`backend/app/routers/packages.py:417`, `backend/app/routers/packages.py:441`).
- Activation/deactivation constraints are present (`backend/app/routers/packages.py:455`, `backend/app/routers/packages.py:491`).
- **Risk:** test suite assumes delete-by-package endpoint that router does not expose (`API_tests/test_packages.py:53`, `backend/app/routers/packages.py:565`).

### 4.2 Catalog + Attachments

- Upload path validates file properties and computes/stores SHA-256 (`backend/app/routers/catalog.py:479`, `backend/app/routers/catalog.py:506`).
- Download path checks integrity before return (`backend/app/routers/catalog.py:562`).
- Dedicated verify endpoint supports offline integrity checks (`backend/app/routers/catalog.py:587`).
- Role protections are consistently attached to mutating operations (`backend/app/routers/catalog.py:127`, `backend/app/routers/catalog.py:313`).

### 4.3 Reviews + Moderation

- Follow-up and image controls are implemented (`backend/app/routers/reviews.py:299`, `backend/app/routers/reviews.py:405`).
- Moderator-only actions are role-gated (`backend/app/routers/reviews.py:678`, `backend/app/routers/reviews.py:701`).
- Frontend query contract appears partially out of sync: sends `search` and `verified_only` while backend list signature does not include these params (`frontend/src/views/ReviewsView.vue:406`, `frontend/src/views/ReviewsView.vue:409`, `backend/app/routers/reviews.py:517`).

### 4.4 CMS Workflow + Sitemap

- Workflow transitions and rollback logic are explicit (`backend/app/routers/cms.py:334`, `backend/app/routers/cms.py:362`, `backend/app/routers/cms.py:478`).
- Revision cap/pruning behavior exists (`backend/app/routers/cms.py:7`, `backend/app/routers/cms.py:84`).
- Sitemap JSON/XML endpoints lack auth dependency (`backend/app/routers/cms.py:551`, `backend/app/routers/cms.py:580`).
- **Manual Verification Required:** confirm whether sitemap must be authenticated or public by requirement.

### 4.5 Messages + Virtual Relay

- Thread and alias relay behavior are documented in code and implemented (`backend/app/routers/messages.py:12`, `backend/app/routers/messages.py:349`).
- Participant authorization helper denies non-members (`backend/app/routers/messages.py:98`).
- Encryption path is present via shared encryptor/decryptor flow (`backend/app/routers/messages.py:407`, `backend/app/core/encryption.py:22`).

### 4.6 Notifications + Admin External API

- Notification retrieval triggers due-retry processing (`backend/app/routers/notifications.py:191`, `backend/app/routers/notifications.py:194`).
- Admin metrics endpoint is role-restricted (`backend/app/routers/notifications.py:307`, `backend/app/routers/notifications.py:310`).
- External admin endpoints require API key, enforce IP allowlist and rate limits (`backend/app/routers/admin.py:106`, `backend/app/routers/admin.py:131`, `backend/app/routers/admin.py:141`).
- Retry schedule is constant-backed, not env-driven as documented (`backend/app/models/notification.py:11`, `README.md:285`).

## 5) Severity-Rated Issues

### Blocker

1. **Hardcoded default cryptographic keys present in runtime config**
   - `SECRET_KEY` and `ENCRYPTION_KEY` are hardcoded defaults in application settings (`backend/app/config.py:7`, `backend/app/config.py:8`).
   - Same values are present in `.env.example` (`backend/.env.example:15`, `backend/.env.example:28`).
   - Risk: if not overridden at deployment, JWT signing and field encryption become predictable/shared.

### High

1. **Delivery test contract drift: package delete path expected by tests but not implemented**
   - Tests call `DELETE /api/packages/{id}` for cleanup (`API_tests/test_packages.py:53`, `API_tests/test_packages.py:123`).
   - Router exposes item-removal delete only (`backend/app/routers/packages.py:565`), no package delete route decorator exists.
   - Impact: acceptance tests can fail or leave data residue, reducing delivery confidence.

2. **Config/documentation mismatch for login lockout controls**
   - README claims env-tunable `MAX_LOGIN_ATTEMPTS` and `LOGIN_LOCKOUT_MINUTES` (`README.md:286`, `README.md:287`).
   - Runtime uses hardcoded constants in auth and token store (`backend/app/routers/auth.py:41`, `backend/app/core/token_store.py:73`).
   - Impact: operational controls do not match declared configurability.

3. **Config/documentation mismatch for notification retry schedule**
   - README declares `NOTIFICATION_RETRY_SCHEDULE_MINUTES` (`README.md:285`).
   - Runtime schedule is constant list in model/core (`backend/app/models/notification.py:11`, `backend/app/core/notification_delivery.py:97`).
   - Impact: deployment-time retry tuning is not actually available.

### Medium

1. **Potential CMS access policy mismatch: sitemap endpoints unauthenticated**
   - `GET /cms/sitemap.json` and `GET /cms/sitemap.xml` have no auth dependencies (`backend/app/routers/cms.py:551`, `backend/app/routers/cms.py:580`).
   - Impact depends on product requirement; could be intended public behavior.
   - **Manual Verification Required**.

2. **Frontend/backend review filter contract mismatch**
   - Frontend sends `search` and `verified_only` (`frontend/src/views/ReviewsView.vue:406`, `frontend/src/views/ReviewsView.vue:409`).
   - Backend list endpoint accepts `subject_text`, `rating_min`, etc., but no `search`/`verified_only` args (`backend/app/routers/reviews.py:517`, `backend/app/routers/reviews.py:520`).
   - Impact: UI filters may silently not apply.

3. **RBAC test payload mismatch on package schema field name**
   - `test_rbac.py` uses `validity_days` (`API_tests/test_rbac.py:96`).
   - Package API uses `validity_window_days` in active tests/router logic (`API_tests/test_packages.py:37`, `backend/app/routers/packages.py:276`).

### Low

1. **Review API tests are intentionally broad due missing order pipeline setup**
   - File states it does not create real orders and validates broad status ranges (`API_tests/test_reviews.py:4`, `API_tests/test_reviews.py:42`).
   - Impact: lower precision for business-rule regressions.

## 6) Security Summary

- **Auth entry points:** login/refresh/logout/logout-all implemented with token/session handling (`backend/app/routers/auth.py:57`, `backend/app/routers/auth.py:150`, `backend/app/routers/auth.py:223`, `backend/app/routers/auth.py:261`).
- **Route/function/object authz:** broad use of `require_role` / `get_current_user` across routers (`backend/app/routers/packages.py:248`, `backend/app/routers/catalog.py:127`, `backend/app/routers/reviews.py:678`, `backend/app/routers/admin.py:167`); object-level participant check in messages (`backend/app/routers/messages.py:98`).
- **User/tenant isolation:** user model has no explicit tenant/store binding (`backend/app/models/user.py:19`, `backend/app/models/user.py:26`); store-scoped filtering exists in feature routes but binding enforcement to user tenancy is not evident statically (`backend/app/routers/reviews.py:565`). **Cannot Confirm Statistically**.
- **Admin/internal endpoint protection:** admin routes are JWT role-gated except explicitly external API-key routes (`backend/app/routers/admin.py:13`, `backend/app/routers/admin.py:456`), with API key expiry, allowlist, and rate-limiting checks (`backend/app/routers/admin.py:125`, `backend/app/routers/admin.py:133`, `backend/app/routers/admin.py:141`).
- **Defense-in-depth:** local-network middleware and hardened headers (`backend/app/main.py:41`, `backend/app/core/security_middleware.py:89`, `backend/app/core/security_middleware.py:52`); log redaction installed (`backend/app/main.py:23`, `backend/app/core/log_filter.py:61`).

## 7) Tests / Logging Review

- Test suites exist for API/unit/frontend and are documented (`README.md:196`, `README.md:219`, `README.md:222`).
- This audit did not execute tests by design (static-only boundary).
- Logging and redaction are centrally configured (`backend/app/main.py:23`, `backend/app/core/log_filter.py:48`).
- Audit event hooks are used across sensitive flows (e.g., auth lock/failure) (`backend/app/routers/auth.py:64`, `backend/app/routers/auth.py:94`).

## 8) Test Coverage Assessment

### 8.1 Current Static Coverage Map

- **Auth/security:** present (`API_tests/test_auth.py`, `unit_tests/test_security.py`, `unit_tests/test_rate_limiter.py`).
- **Catalog/file integrity:** present (`API_tests/test_catalog.py`, `unit_tests/test_file_utils.py`).
- **Packages/versioning:** present but with cleanup-contract drift (`API_tests/test_packages.py:53`, `backend/app/routers/packages.py:565`).
- **Reviews:** present but intentionally shallow for order-dependent business rules (`API_tests/test_reviews.py:4`).
- **CMS/notifications/admin/messages:** present (`API_tests/test_cms.py`, `API_tests/test_notifications.py`, `API_tests/test_admin.py`, `API_tests/test_messages.py`).
- **Frontend logic:** present in view/store-level Vitest suites (`frontend/src/__tests__/router.test.js`, `frontend/src/__tests__/cmsWorkflow.test.js`).

### 8.2 Minimum Test Additions Required

1. Add/align package deletion behavior: either implement `DELETE /api/packages/{id}` or remove that assumption from tests.
2. Add contract tests ensuring review list filters sent by frontend are recognized server-side (or frontend updated to backend params).
3. Add config-driven tests for lockout/retry settings if env configurability is required.
4. Add explicit tests for sitemap access policy (authenticated vs public) to lock requirement intent.
5. Add stronger end-to-end review tests with real order setup to validate completion-only and ownership rules.

### 8.3 Coverage Judgment

**Coverage Verdict: Partial Pass.**

- Breadth is decent across domains, but precision gaps and API-contract drift reduce acceptance confidence.

## 9) Final Notes

- Strong architectural foundation exists for offline operation, RBAC routing, encryption-at-rest fields, and notification/admin workflows.
- Final acceptance should be gated on resolving section 5 Blocker/High issues.
- After fixes, perform a runtime verification pass (manual + automated) focused on auth lockout behavior, notification retry timing, sitemap access policy, and package/review API contracts.
