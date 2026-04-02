# TraceCare Offline Compliance Portal - Design

## Product Intent

TraceCare is a single offline portal that combines:

- Clinic physical exam package management and operations
- Agricultural product catalog and traceability management

Both domains share one role model, one authentication system, one message/reminder center, and one admin console.

## High-Level Architecture

- Frontend: Vue 3 + Vite SPA (`repo/frontend`)
- Backend: FastAPI REST API (`repo/backend`)
- Database: PostgreSQL (primary system of record)
- Storage: Local filesystem for attachments/images under `uploads`
- Runtime model: Fully offline/on-prem, localhost/private network only

## Core Modules

1. Identity and Access
- Local username/password login
- Role-based authorization (Administrator, Clinic Staff, Catalog Manager, End User)
- Token refresh/rotation and logout controls

2. Clinic Exam Dictionary and Packages
- Exam item dictionary stores clinical metadata (ranges, units, constraints, methods)
- Package builder composes versioned sets of exam item snapshots
- Version diff endpoint allows staff to inspect "what changed"

3. Agricultural Catalog and Traceability
- Product/catalog entities hold category/spec attributes
- Trace events map product movement/state over time
- Local file attachment pipeline supports MIME, size, and fingerprint checks

4. Reviews and Credibility
- Reviews tied to completed order context
- Follow-up reviews and moderation controls (pin/collapse)
- Local, auditable credibility scoring rule in backend logic

5. CMS and Content Lifecycle
- Draft -> review -> publish flow
- Revision history and rollback support
- Offline sitemap export outputs (JSON/XML)

6. Message and Reminder Center
- Conversation threads tied to order context
- Unread counters and read/archive actions
- Notification preferences and local delivery metrics

7. Admin Console
- Site rules, tasks, system parameters
- Proxy pool (internal network routing only)
- CSV/data export and API key lifecycle for on-prem integrations

8. Audit and Security
- Audit logs for key actions
- Security middleware for offline/local-only enforcement
- Sensitive-data redaction and encrypted fields at rest

## Data and Integrity Patterns

- PostgreSQL is the source of truth for operational entities.
- Package composition persists item snapshots to preserve historical integrity when dictionaries evolve.
- File attachments are stored locally and validated before persistence.
- Security-sensitive values are masked in logs and encrypted where required.

## Request/Response Flow

1. User authenticates in Vue app.
2. Frontend includes token for protected API calls.
3. FastAPI middleware enforces network/security constraints.
4. Routers execute role checks, validation, and domain logic.
5. SQLAlchemy persists/retrieves PostgreSQL records.
6. Optional file assets are read/write from local filesystem.
7. Frontend renders updated state and unread/delivery counters.

## Frontend Design Notes

- Router-level role guards protect page access by user role.
- Major route groups mirror backend modules: exams, packages, catalog, reviews, messages, notifications, CMS, admin.
- Quick views provide saved search/filter presets for repeated user workflows.

## Non-Functional Design Goals

- Offline-first: no external cloud dependencies for core flows.
- Traceability: preserve version history and auditability across edits.
- Security by default: strict local-network constraints and sensitive-data handling.
- Operability: clear admin controls for system parameters, exports, tasks, and integration keys.

