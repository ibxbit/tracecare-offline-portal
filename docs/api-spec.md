# TraceCare Offline Compliance Portal - API Spec

Base URL: `http://localhost:8000/api`

## Overview

- Backend framework: FastAPI
- Data store: PostgreSQL
- Auth style: local username/password + access/refresh tokens
- Deployment style: offline/on-prem (localhost or private LAN)
- Health check: `GET /health`

## Security and Access

- Password hashing uses Argon2id (from backend dependencies).
- Sensitive data is encrypted/masked in logs by security middleware and filters.
- Session/refresh tokens are used for authenticated endpoints.
- Role-based access is enforced for admin/staff/cross-functional operations.
- External integration API keys are supported in admin endpoints and constrained by local rate limits.

## Authentication

Prefix: `/auth`

- `POST /auth/login` - Sign in with local credentials and receive tokens.
- `POST /auth/refresh` - Rotate/refresh access token.
- `POST /auth/logout` - Invalidate current session/token.
- `POST /auth/logout-all` - Invalidate all sessions for the user.

## Users

Prefix: `/users`

- `GET /users/me` - Current authenticated user profile.
- `PUT /users/me` - Update own profile details.
- `POST /users/me/change-password` - Update password.
- `GET /users/{user_id}` - Get user by id (authorized roles).
- `PUT /users/{user_id}` - Update a user (authorized roles).
- `DELETE /users/{user_id}` - Soft/hard remove user based on implementation rules.

## Exam Item Dictionary

Prefix: `/exam-items`

- `GET /exam-items` - List exam dictionary items (filter/search supported in implementation).
- `POST /exam-items` - Create new exam dictionary item.
- `GET /exam-items/{item_id}` - Get item detail.
- `PUT /exam-items/{item_id}` - Update item.
- `PATCH /exam-items/{item_id}/reactivate` - Reactivate item.
- `DELETE /exam-items/{item_id}` - Deactivate/remove item.

## Exam Packages and Versioning

Prefix: `/packages`

- `GET /packages` - List packages.
- `POST /packages` - Create package.
- `GET /packages/{package_id}` - Get package detail.
- `GET /packages/{package_id}/versions` - List package versions.
- `POST /packages/{package_id}/new-version` - Create next version from existing package.
- `GET /packages/{package_id}/diff/{other_id}` - Compare two package versions.
- `PATCH /packages/{package_id}/activate` - Activate package/version.
- `PATCH /packages/{package_id}/deactivate` - Deactivate package/version.
- `POST /packages/{package_id}/items` - Add item snapshot to package.
- `DELETE /packages/{package_id}/items/{exam_item_id}` - Remove item from package.

## Exams

Prefix: `/exams`

- `GET /exams` - List exams/orders in clinic workflow.
- `POST /exams` - Create exam/order entry.
- `GET /exams/{exam_id}` - Get exam/order detail.
- `PUT /exams/{exam_id}` - Update exam/order.
- `DELETE /exams/{exam_id}` - Remove exam/order entry.

## Products and Traceability

Prefixes: `/products`, `/catalog`

Products:
- `GET /products` - List products.
- `POST /products` - Create product.
- `GET /products/{product_id}` - Product detail.
- `PUT /products/{product_id}` - Update product.
- `DELETE /products/{product_id}` - Delete/deactivate product.
- `GET /products/{product_id}/trace-events` - Traceability timeline/events.

Catalog:
- `GET /catalog` - List searchable catalog entries.
- `POST /catalog` - Create catalog entry.
- `GET /catalog/{item_id}` - Catalog detail.
- `PUT /catalog/{item_id}` - Update catalog item.
- `PATCH /catalog/{item_id}/deactivate` - Deactivate item.
- `PATCH /catalog/{item_id}/reactivate` - Reactivate item.
- `PUT /catalog/{item_id}/stock` - Stock delta update.
- `PUT /catalog/{item_id}/stock/set` - Absolute stock set.
- `GET /catalog/{item_id}/attachments` - List attachments.
- `POST /catalog/{item_id}/attachments` - Upload attachment.
- `GET /catalog/{item_id}/attachments/{att_id}/download` - Download attachment.
- `DELETE /catalog/{item_id}/attachments/{att_id}` - Remove attachment.
- `GET /catalog/meta/allowed-mime-types` - Allowed local upload MIME list.

## Reviews

Prefix: `/reviews`

- `GET /reviews` - List reviews with moderation-aware ordering.
- `POST /reviews` - Create review (1-5 stars, text, tags, images constraints in schemas).
- `GET /reviews/summary` - Aggregated score/volume summary.
- `GET /reviews/{review_id}` - Review detail.
- `POST /reviews/{review_id}/followup` - Create one follow-up review (bounded window).
- `PATCH /reviews/{review_id}/pin` - Pin review.
- `PATCH /reviews/{review_id}/unpin` - Unpin review.
- `PATCH /reviews/{review_id}/collapse` - Collapse review.
- `PATCH /reviews/{review_id}/uncollapse` - Uncollapse review.
- `GET /reviews/{review_id}/images/{image_id}/download` - Download review image.
- `DELETE /reviews/{review_id}/images/{image_id}` - Delete review image.
- `DELETE /reviews/{review_id}` - Delete review.

## Messages and Reminder Center

Prefixes: `/messages`, `/notifications`

Messages:
- `GET /messages/inbox` - Inbox listing.
- `GET /messages/sent` - Sent listing.
- `GET /messages/inbox/unread-count` - Unread message count.
- `GET /messages/{message_id}` - Message detail.
- `PATCH /messages/{message_id}/read` - Mark as read.
- `DELETE /messages/{message_id}` - Delete message.
- `POST /messages/threads` - Create conversation thread.
- `GET /messages/threads` - List threads.
- `GET /messages/threads/{thread_id}` - Thread detail.
- `PATCH /messages/threads/{thread_id}/read` - Mark thread as read.
- `PATCH /messages/threads/{thread_id}/archive` - Archive thread.
- `GET /messages/threads/{thread_id}/my-alias` - Get masked virtual contact identifier.

Notifications:
- `GET /notifications` - List in-app notifications.
- `GET /notifications/unread-count` - Unread notification count.
- `GET /notifications/{notif_id}` - Notification detail.
- `PATCH /notifications/{notif_id}/read` - Mark read.
- `POST /notifications/mark-read` - Mark multiple as read.
- `POST /notifications/mark-all-read` - Mark all as read.
- `DELETE /notifications/{notif_id}` - Delete notification.
- `GET /notifications/admin/metrics` - Local delivery success/failure counters.
- `GET /notifications/preferences/me` - Current user preferences.
- `PUT /notifications/preferences/me` - Update preferences.

## CMS

Prefix: `/cms`

- `POST /cms/pages` - Create page draft.
- `GET /cms/pages` - List pages.
- `GET /cms/pages/export` - Export pages for offline transport.
- `GET /cms/pages/{page_id}` - Page detail.
- `GET /cms/pages/by-slug/{slug}` - Fetch page by slug.
- `PUT /cms/pages/{page_id}` - Update page.
- `DELETE /cms/pages/{page_id}` - Delete page.
- `POST /cms/pages/{page_id}/submit-review` - Draft to review.
- `POST /cms/pages/{page_id}/approve` - Review to publish.
- `POST /cms/pages/{page_id}/reject` - Reject review.
- `POST /cms/pages/{page_id}/archive` - Archive published page.
- `POST /cms/pages/{page_id}/restore` - Restore archived page.
- `GET /cms/pages/{page_id}/revisions` - Revision list.
- `GET /cms/pages/{page_id}/revisions/{revision_number}` - Revision detail.
- `POST /cms/pages/{page_id}/rollback/{revision_number}` - One-click rollback.
- `GET /cms/pages/{page_id}/preview` - Render preview.
- `GET /cms/sitemap.json` - JSON sitemap.
- `GET /cms/sitemap.xml` - XML sitemap.

## Admin Console and External Integrations

Prefix: `/admin`

Site Rules:
- `POST /admin/rules`
- `GET /admin/rules`
- `GET /admin/rules/{rule_id}`
- `PUT /admin/rules/{rule_id}`
- `PATCH /admin/rules/{rule_id}/toggle`
- `DELETE /admin/rules/{rule_id}`

System Parameters:
- `GET /admin/parameters`
- `GET /admin/parameters/{key}`
- `PUT /admin/parameters/{key}`

Task Management:
- `POST /admin/tasks`
- `GET /admin/tasks`
- `GET /admin/tasks/{task_id}`
- `PATCH /admin/tasks/{task_id}/status`
- `DELETE /admin/tasks/{task_id}`

Proxy Pool (internal routing use only):
- `POST /admin/proxy-pool`
- `GET /admin/proxy-pool`
- `GET /admin/proxy-pool/{proxy_id}`
- `PUT /admin/proxy-pool/{proxy_id}`
- `PATCH /admin/proxy-pool/{proxy_id}/health-check`
- `DELETE /admin/proxy-pool/{proxy_id}`

API Keys + Exports + Status:
- `POST /admin/api-keys`
- `GET /admin/api-keys`
- `GET /admin/api-keys/{key_id}`
- `PUT /admin/api-keys/{key_id}`
- `PATCH /admin/api-keys/{key_id}/rotate`
- `PATCH /admin/api-keys/{key_id}/toggle`
- `DELETE /admin/api-keys/{key_id}`
- `GET /admin/export/site-rules`
- `GET /admin/export/tasks`
- `GET /admin/export/users`
- `GET /admin/export/api-keys`
- `GET /admin/system/status`

## Audit

Prefix: `/audit`

- `GET /audit` - List audit records.
- `GET /audit/{log_id}` - Audit record detail.

