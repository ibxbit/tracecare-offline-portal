# Review of Previously Encountered Errors — TraceCare Offline Compliance Portal

## Summary
This report reviews the previously encountered fail-causing issues and verifies their current status based on static code and test evidence. All findings are traceable to file and line number where possible.

---

### 1. CMS workflow/rollback request body contract mismatch
**Status:** Fixed
- All CMS workflow and rollback POSTs (submit-review, approve, reject, archive, restore, rollback) require and receive a body with `{ "note": ... }`.
- No endpoints or tests allow empty-body POSTs.
- Rollback and all workflow actions use the correct contract.
- **Evidence:**
  - `repo/backend/app/schemas/cms.py` (WorkflowTransitionRequest)
  - `repo/API_tests/test_cms.py` (TestCMSWorkflow)
  - `repo/frontend/src/views/CMSView.vue` (workflowAction, rollback)

### 2. CMS reject key mismatch (`reason` vs `note`)
**Status:** Fixed
- All code and tests use `note` (not `reason`) for CMS reject actions.
- No `reason` key is sent in any workflow/test/contract.
- The frontend label still says "Reason (optional)" but the payload is always `{ note: ... }`.
- **Evidence:**
  - `repo/frontend/src/views/CMSView.vue` (handleReject)
  - `repo/API_tests/test_cms.py` (TestCMSWorkflow)
  - `repo/frontend/src/__tests__/cmsWorkflow.test.js`

### 3. Review UI cannot submit valid `exam_type` payload
**Status:** Fixed
- Frontend requires `subject_text` for `exam_type` and does not require `subject_id`.
- For other types, `subject_id` is required and `subject_text` is not sent.
- API tests and backend schema enforce this logic.
- **Evidence:**
  - `repo/frontend/src/views/ReviewsView.vue` (createForm, handleCreate)
  - `repo/API_tests/test_reviews.py` (TestReviewCreation)
  - `repo/backend/app/schemas/review.py` (ReviewCreate)

### 4. Test/Coverage Hardening
**Status:** Fixed
- API and frontend tests explicitly check for correct workflow/rollback contract and review payload validation.
- No test regressions found in code.
- **Evidence:**
  - `repo/API_tests/test_cms.py`
  - `repo/API_tests/test_reviews.py`
  - `repo/frontend/src/__tests__/cmsWorkflow.test.js`

### 5. Quality Requirements
- **Offline-only behavior:** No evidence of online dependencies in core flows.
- **RBAC/security:** RBAC and security logic present and enforced in backend and tests.
- **API contracts:** Consistent across backend, frontend, and tests.
- **README/docs:** Contracts and flows are documented; see `repo/README.md`, `repo/docs/api-spec.md`.

---

## Conclusion
All previously encountered fail-causing issues have been fixed based on static evidence. No regressions found. Manual/runtime verification is still recommended for final acceptance.

---

**Report generated:** 2026-04-08
