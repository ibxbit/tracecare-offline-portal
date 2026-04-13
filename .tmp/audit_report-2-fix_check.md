# Audit Issue Re-Review — April 13, 2026

## Blocker/High Issues (from previous audit)

### 1. Hardcoded default cryptographic keys in config
- **Status:** Fixed
- Evidence: `backend/app/config.py` has no hardcoded fallback secrets; `.env.example` and `README.md` require strong secrets.

### 2. Package delete API/test contract drift
- **Status:** Fixed
- Evidence: `DELETE /api/packages/{package_id}` implemented in `backend/app/routers/packages.py`.

### 3. Login lockout config not env-driven
- **Status:** Fixed
- Evidence: `MAX_LOGIN_ATTEMPTS` and `LOGIN_LOCKOUT_MINUTES` are env/config-driven in both `routers/auth.py` and `core/token_store.py`.

### 4. Notification retry schedule not env-driven
- **Status:** Fixed
- Evidence: `NOTIFICATION_RETRY_SCHEDULE_MINUTES` is env/config-driven in `models/notification.py`.

### 5. Reviews frontend/backend filter contract mismatch
- **Status:** Partially Fixed
- Evidence: Frontend sends `search` and `verified_only` params, but backend does not accept them. No backend-side support for these filters yet.

## Medium/Other Issues
- **CMS sitemap endpoint auth:** Not changed; still requires manual policy confirmation.
- **RBAC test payload mismatch:** Not checked in this review.

## Summary
- All Blocker and High issues from the previous audit have been fixed in code and config.
- One Medium issue (frontend/backend review filter contract) remains partially fixed.
- Manual review still required for CMS sitemap endpoint policy.

---