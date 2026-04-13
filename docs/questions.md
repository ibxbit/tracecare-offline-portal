# TraceCare Business Gap Questions

Question: Should package validity be auto-expired by a scheduler when the publish window ends, or only checked at purchase/runtime?

Hypothesis: Runtime checks already block invalid usage, but stale "active" records can confuse staff and end users.

Solution: Confirm the intended expiry mechanism first. The reviewed repo surfaces do not show a clear package-expiry scheduler yet, so any cleanup job should be implemented explicitly rather than assumed.

---

Question: For review anti-spam, should the 10-minute retry limit be enforced per order globally or per user-order pair?

Hypothesis: Per user-order is safer for shared kiosk/device environments and aligns with account-level accountability.

Solution: Keep limiter key scoped to `user_id + order_id` and return a clear retry-after message in API responses.

---

Question: Should the "one follow-up review within 14 days" window use order completion time or initial review creation time?

Hypothesis: Using order completion time gives deterministic policy and avoids ambiguity when first review is delayed.

Solution: Enforce follow-up eligibility against the order completion timestamp and expose the remaining window in review detail.

---

Question: How should masked-number relay behave when users are allowed to see conversation context but not direct contacts?

Hypothesis: A stable per-thread virtual alias preserves continuity while preventing leakage of real phone/contact data.

Solution: Continue using thread-level virtual contact identifiers (`my-alias`) and block raw contact fields from responses.

---

Question: The prompt mentions optional multi-store and multilingual CMS variants; should this be mandatory in current milestone?

Hypothesis: Current implementation can operate single-store/single-language first, with schema hooks for phased expansion.

Solution: Track as phase-2 scope; keep current workflow (draft/review/publish/revisions/rollback) and add store/locale dimensions in next increment.

---

Question: For catalog attachments with file fingerprints, do we reject duplicate fingerprints globally or allow duplicates with audit warnings?

Hypothesis: Some files may legitimately repeat across batches/products, so hard rejection may block valid operations.

Solution: Allow duplicate fingerprints but emit warning-level audit records and expose duplicates in admin review tooling.

---

Question: Notifications are offline-only with retries at 1/5/15 minutes; what is final state after all retries fail?

Hypothesis: Operators need explicit terminal status for troubleshooting and SLA metrics.

Solution: Mark terminal status as failed after retry exhaustion, store fail reason locally, and include it in admin delivery metrics.

---

Question: Admin proxy pool is internal-routing-only; should proxies be selectable per task type or globally active?

Hypothesis: Per-task assignment gives better control and traceability for external-system triggers from on-prem integrations.

Solution: Add task-level proxy binding in admin task forms and persist this mapping in audit logs.

