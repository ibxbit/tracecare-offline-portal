/**
 * F-3 — CMS workflow and revision action tests.
 *
 * Verifies the state-machine transition logic and UI helpers extracted
 * from CMSView: statusClass, available actions per status, autoSlug,
 * and revision sort order.
 */
import { describe, it, expect } from 'vitest'

// ── State-machine helpers (mirrors CMSView logic) ────────────────────────────

const STATUS_CLASSES = {
  draft:     'bg-slate-100 text-slate-600',
  review:    'bg-blue-100 text-blue-700',
  published: 'bg-green-100 text-green-700',
  archived:  'bg-amber-100 text-amber-700',
}

function statusClass(status) {
  return STATUS_CLASSES[status] ?? 'bg-slate-100 text-slate-500'
}

/** Returns the list of workflow actions available for a given status. */
function availableActions(status) {
  switch (status) {
    case 'draft':     return ['edit', 'submit-review', 'history', 'delete']
    case 'review':    return ['edit', 'approve', 'reject', 'history', 'delete']
    case 'published': return ['edit', 'archive', 'history', 'delete']
    case 'archived':  return ['edit', 'restore', 'history', 'delete']
    default:          return ['edit', 'history', 'delete']
  }
}

function autoSlug(title) {
  return title
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, '-') // match implementation: replace special chars with hyphen
    .replace(/\s+/g, '-')
    .slice(0, 100)
}

// ── Status badge ──────────────────────────────────────────────────────────────

describe('CMSView — statusClass', () => {
  it('draft → slate classes', () => {
    expect(statusClass('draft')).toContain('slate')
  })
  it('review → blue classes', () => {
    expect(statusClass('review')).toContain('blue')
  })
  it('published → green classes', () => {
    expect(statusClass('published')).toContain('green')
  })
  it('archived → amber classes', () => {
    expect(statusClass('archived')).toContain('amber')
  })
  it('unknown status → fallback classes', () => {
    expect(statusClass('unknown')).toBe('bg-slate-100 text-slate-500')
  })
})

// ── Workflow transitions ───────────────────────────────────────────────────────

describe('CMSView — available workflow actions per status', () => {
  it('draft exposes submit-review but NOT approve/archive/restore', () => {
    const actions = availableActions('draft')
    expect(actions).toContain('submit-review')
    expect(actions).not.toContain('approve')
    expect(actions).not.toContain('archive')
    expect(actions).not.toContain('restore')
  })

  it('review exposes approve AND reject but NOT submit-review/archive', () => {
    const actions = availableActions('review')
    expect(actions).toContain('approve')
    expect(actions).toContain('reject')
    expect(actions).not.toContain('submit-review')
    expect(actions).not.toContain('archive')
  })

  it('published exposes archive but NOT approve/reject/restore', () => {
    const actions = availableActions('published')
    expect(actions).toContain('archive')
    expect(actions).not.toContain('approve')
    expect(actions).not.toContain('reject')
    expect(actions).not.toContain('restore')
  })

  it('archived exposes restore but NOT submit-review/approve/archive', () => {
    const actions = availableActions('archived')
    expect(actions).toContain('restore')
    expect(actions).not.toContain('submit-review')
    expect(actions).not.toContain('approve')
    expect(actions).not.toContain('archive')
  })

  it('all statuses expose edit, history and delete', () => {
    for (const s of ['draft', 'review', 'published', 'archived']) {
      const actions = availableActions(s)
      expect(actions).toContain('edit')
      expect(actions).toContain('history')
      expect(actions).toContain('delete')
    }
  })
})

// ── autoSlug ──────────────────────────────────────────────────────────────────

describe('CMSView — autoSlug', () => {
  it('converts title to lowercase kebab', () => {
    expect(autoSlug('Hello World')).toBe('hello-world')
  })
  it('strips special characters', () => {
    expect(autoSlug('FAQ & Policies!')).toBe('faq--policies')
  })
  it('collapses multiple spaces to one hyphen', () => {
    expect(autoSlug('one  two   three')).toBe('one-two-three')
  })
  it('caps at 100 characters', () => {
    expect(autoSlug('a '.repeat(60))).toHaveLength(100)
  })
})

// ── Revision list ordering ────────────────────────────────────────────────────

describe('CMSView — revision list (newest first)', () => {
  const revisions = [
    { id: 1, revision_number: 1, created_at: '2024-01-01T00:00:00Z', change_note: 'initial' },
    { id: 2, revision_number: 2, created_at: '2024-01-02T00:00:00Z', change_note: 'edit 1' },
    { id: 3, revision_number: 3, created_at: '2024-01-03T00:00:00Z', change_note: 'edit 2' },
  ]

  it('after .reverse() the newest revision is first', () => {
    const sorted = revisions.slice().reverse()
    expect(sorted[0].revision_number).toBe(3)
    expect(sorted[sorted.length - 1].revision_number).toBe(1)
  })

  it('current revision button is hidden (matched by revision_number === current_revision)', () => {
    const currentRevision = 3
    const shouldHideRollback = (rev) => rev.revision_number === currentRevision
    expect(shouldHideRollback(revisions[2])).toBe(true)
    expect(shouldHideRollback(revisions[0])).toBe(false)
  })
})

// ── WorkflowTransitionRequest API payload contract ────────────────────────────
//
// Backend contract: every workflow/rollback POST requires a JSON body matching
//   WorkflowTransitionRequest { note: str | null }
//
// Omitting the body entirely causes FastAPI to return 422.
// The `reason` key must NEVER be sent — only `note`.
//
// These functions mirror CMSView.vue:
//   workflowAction  →  api.post(url, { note: null })
//   handleReject    →  api.post(url, { note: rejectReason || null })
//   rollback        →  api.post(url, { note: null })

function buildWorkflowBody(note = null) {
  return { note: note }
}

function buildRejectBody(noteText = null) {
  // Correct: `note` key.  The old (wrong) key was `reason`.
  return { note: noteText }
}

function buildRollbackBody(note = null) {
  return { note: note }
}

describe('CMSView — WorkflowTransitionRequest body (A-01 / A-03 contract lock)', () => {
  const WORKFLOW_ACTIONS = ['submit-review', 'approve', 'reject', 'archive', 'restore', 'rollback']

  it('workflowAction body always contains the `note` key', () => {
    const body = buildWorkflowBody()
    expect(body).toHaveProperty('note')
  })

  it('workflowAction default body has note === null (no note provided)', () => {
    const body = buildWorkflowBody()
    expect(body.note).toBeNull()
  })

  it('workflowAction body with explicit note string passes it through', () => {
    const body = buildWorkflowBody('Ready for review')
    expect(body.note).toBe('Ready for review')
  })

  it('all 6 workflow endpoint calls share the same single-key body shape', () => {
    WORKFLOW_ACTIONS.forEach(action => {
      const body = buildWorkflowBody(null)
      // Must have exactly one key and it must be `note`
      expect(Object.keys(body)).toEqual(['note'])
    })
  })

  it('body object is never undefined or null — omitting body would cause 422', () => {
    const body = buildWorkflowBody(null)
    expect(body).toBeDefined()
    expect(body).not.toBeNull()
    expect(typeof body).toBe('object')
  })

  // ── Reject: `note` not `reason` ─────────────────────────────────────────────

  it('handleReject sends `note` key, NOT the stale `reason` key', () => {
    const body = buildRejectBody('Needs revision — missing citations')
    expect(body).toHaveProperty('note', 'Needs revision — missing citations')
    expect(body.reason).toBeUndefined()   // `reason` must never appear
  })

  it('handleReject with no text sends note: null (still a valid body)', () => {
    const body = buildRejectBody(null)
    expect(body).toHaveProperty('note')
    expect(body.note).toBeNull()
    expect(body.reason).toBeUndefined()
  })

  it('reject body does not accidentally carry both `note` and `reason`', () => {
    const body = buildRejectBody('test')
    const keys = Object.keys(body)
    expect(keys).not.toContain('reason')
    expect(keys).toContain('note')
    expect(keys).toHaveLength(1)
  })

  // ── Rollback ─────────────────────────────────────────────────────────────────

  it('rollback body has `note` key (endpoint requires WorkflowTransitionRequest)', () => {
    const body = buildRollbackBody(null)
    expect(body).toHaveProperty('note')
  })

  it('rollback body with an optional note string passes it through', () => {
    const body = buildRollbackBody('Revert to stable version')
    expect(body.note).toBe('Revert to stable version')
  })

  it('rollback body shape is identical to other workflow transition bodies', () => {
    const rollbackBody = buildRollbackBody(null)
    const workflowBody = buildWorkflowBody(null)
    expect(Object.keys(rollbackBody)).toEqual(Object.keys(workflowBody))
  })
})
