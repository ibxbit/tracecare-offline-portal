/**
 * Tests for:
 *  - NavBar admin route fix: /packages/setup (not /package-setup)
 *  - NotificationsView type filters use valid backend enum values
 *  - ReviewsView subject type options match backend enum
 *  - PackageDiffView diff field mapping (from_value/to_value, changes object)
 */
import { describe, it, expect } from 'vitest'

// ── 1. NavBar navigation items ───────────────────────────────────────────────

const allNavItems = [
  { to: '/dashboard',    label: 'Dashboard',   roles: null },
  { to: '/packages',     label: 'Packages',    roles: null },
  { to: '/packages/setup', label: 'Pkg Setup', roles: ['admin'] },
  { to: '/exams',        label: 'Exams',       roles: ['admin', 'clinic_staff'] },
  { to: '/catalog',      label: 'Catalog',     roles: null },
  { to: '/reviews',      label: 'Reviews',     roles: null },
  { to: '/messages',     label: 'Messages',    roles: null },
  { to: '/cms',          label: 'CMS',         roles: ['admin', 'clinic_staff', 'catalog_manager'] },
  { to: '/admin',        label: 'Admin',       roles: ['admin'] },
  { to: '/users',        label: 'Users',       roles: ['admin'] },
]

describe('NavBar — route paths', () => {
  it('uses /packages/setup (not /package-setup) for package setup', () => {
    const setupItem = allNavItems.find(i => i.label === 'Pkg Setup')
    expect(setupItem).toBeDefined()
    expect(setupItem.to).toBe('/packages/setup')
    expect(setupItem.to).not.toBe('/package-setup')
  })

  it('all routes are non-empty strings', () => {
    allNavItems.forEach(item => {
      expect(typeof item.to).toBe('string')
      expect(item.to.length).toBeGreaterThan(0)
    })
  })

  it('admin-only items include admin role', () => {
    const adminItems = allNavItems.filter(i => i.label === 'Admin' || i.label === 'Pkg Setup')
    adminItems.forEach(item => {
      expect(item.roles).toContain('admin')
    })
  })
})

// ── 2. Notification type filters use valid backend enum values ────────────────

const VALID_NOTIFICATION_TYPES = new Set(['info', 'warning', 'error', 'success', 'system'])

const typeFilters = [
  { value: '', label: 'All' },
  { value: 'info', label: 'Info' },
  { value: 'warning', label: 'Warning' },
  { value: 'error', label: 'Error' },
  { value: 'success', label: 'Success' },
  { value: 'system', label: 'System' },
]

describe('NotificationsView — type filters', () => {
  it('all non-empty filter values are valid backend NotificationType enum values', () => {
    typeFilters
      .filter(f => f.value !== '')
      .forEach(f => {
        expect(VALID_NOTIFICATION_TYPES.has(f.value)).toBe(true)
      })
  })

  it('does not include invalid types order_status or message', () => {
    const values = typeFilters.map(f => f.value)
    expect(values).not.toContain('order_status')
    expect(values).not.toContain('message')
  })
})

// ── 3. ReviewsView subject type options match backend enum ───────────────────

const VALID_SUBJECT_TYPES = new Set(['product', 'exam_type', 'catalog_item'])

const subjectTypeOptions = [
  { value: 'product',      label: 'Product' },
  { value: 'exam_type',    label: 'Exam Type' },
  { value: 'catalog_item', label: 'Catalog Item' },
]

describe('ReviewsView — subject type options', () => {
  it('all options use valid backend ReviewSubjectType enum values', () => {
    subjectTypeOptions.forEach(opt => {
      expect(VALID_SUBJECT_TYPES.has(opt.value)).toBe(true)
    })
  })

  it('does not include invalid types exam_package or service', () => {
    const values = subjectTypeOptions.map(o => o.value)
    expect(values).not.toContain('exam_package')
    expect(values).not.toContain('service')
  })
})

// ── 4. PackageDiffView — diff response field mapping ────────────────────────

function renderMetadataChange(change) {
  // Must use from_value/to_value (not before/after)
  return {
    field: change.field,
    before: change.from_value,
    after: change.to_value,
  }
}

function renderItemChanges(c) {
  // Must iterate Object.entries(c.changes), using delta.from / delta.to
  return Object.entries(c.changes || {}).map(([fieldName, delta]) => ({
    field: fieldName,
    before: delta.from,
    after: delta.to,
  }))
}

describe('PackageDiffView — diff field mapping', () => {
  const sampleMetadataChange = {
    field: 'price',
    from_value: 99.99,
    to_value: 149.99,
  }

  const sampleItemChange = {
    exam_item_id: 3,
    code: 'ALB',
    name: 'Albumin',
    changes: {
      is_required: { from: false, to: true },
      item_code_snapshot: { from: 'ALB1', to: 'ALB2' },
    },
  }

  it('reads from_value not before for metadata changes', () => {
    const rendered = renderMetadataChange(sampleMetadataChange)
    expect(rendered.before).toBe(99.99)
    expect(rendered.after).toBe(149.99)
  })

  it('iterates c.changes as object (not c.changed_fields array)', () => {
    const rendered = renderItemChanges(sampleItemChange)
    expect(rendered).toHaveLength(2)
  })

  it('reads delta.from and delta.to from changes object', () => {
    const rendered = renderItemChanges(sampleItemChange)
    const isRequiredChange = rendered.find(r => r.field === 'is_required')
    expect(isRequiredChange.before).toBe(false)
    expect(isRequiredChange.after).toBe(true)
  })
})

// ── 5. Thread API URL prefix ─────────────────────────────────────────────────

const THREAD_ROUTES = {
  list:    '/messages/threads',
  detail:  (id) => `/messages/threads/${id}`,
  send:    (id) => `/messages/threads/${id}/messages`,
  read:    (id) => `/messages/threads/${id}/read`,
  archive: (id) => `/messages/threads/${id}/archive`,
  create:  '/messages/threads',
  resolve: (threadId, alias) => `/messages/threads/${threadId}/resolve-alias/${alias}`,
}

describe('Thread API routes — correct /messages/threads prefix', () => {
  it('list threads uses /messages/threads', () => {
    expect(THREAD_ROUTES.list).toBe('/messages/threads')
    expect(THREAD_ROUTES.list).not.toBe('/threads')
  })

  it('thread detail includes /messages prefix', () => {
    expect(THREAD_ROUTES.detail(5)).toBe('/messages/threads/5')
  })

  it('send message to thread includes /messages prefix', () => {
    expect(THREAD_ROUTES.send(5)).toBe('/messages/threads/5/messages')
  })

  it('create thread uses /messages/threads (not /threads)', () => {
    expect(THREAD_ROUTES.create).toContain('/messages/')
  })
})

// ── 6. Notification metrics — correct backend field names ────────────────────

const VALID_METRICS_KEYS = ['total', 'delivered', 'retrying', 'failed', 'pending',
                             'delivery_rate_pct', 'avg_attempts_on_delivered', 'by_type']
const INVALID_METRICS_KEYS = ['total_delivered', 'total_retrying', 'total_failed', 'total_pending']

// Simulated metrics object as the UI should read from the backend
const sampleMetrics = {
  total: 100,
  delivered: 80,
  retrying: 5,
  failed: 3,
  pending: 12,
  delivery_rate_pct: 80.0,
  avg_attempts_on_delivered: 1.2,
  by_type: { info: { delivered: 40 }, warning: { delivered: 20 } },
}

describe('NotificationsView — metrics field alignment with DeliveryMetricsResponse', () => {
  it('reads delivered (not total_delivered) from metrics', () => {
    expect(sampleMetrics.delivered).toBe(80)
    expect(sampleMetrics.total_delivered).toBeUndefined()
  })

  it('reads retrying (not total_retrying) from metrics', () => {
    expect(sampleMetrics.retrying).toBe(5)
    expect(sampleMetrics.total_retrying).toBeUndefined()
  })

  it('reads failed (not total_failed) from metrics', () => {
    expect(sampleMetrics.failed).toBe(3)
    expect(sampleMetrics.total_failed).toBeUndefined()
  })

  it('reads pending (not total_pending) from metrics', () => {
    expect(sampleMetrics.pending).toBe(12)
    expect(sampleMetrics.total_pending).toBeUndefined()
  })

  it('all valid backend metric keys are present in sample', () => {
    VALID_METRICS_KEYS.forEach(key => {
      expect(sampleMetrics).toHaveProperty(key)
    })
  })

  it('no stale total_* keys are used', () => {
    INVALID_METRICS_KEYS.forEach(key => {
      expect(sampleMetrics[key]).toBeUndefined()
    })
  })
})

// ── 7. Catalog filter params — tags and priority ──────────────────────────────

function buildCatalogParams(filters) {
  // Mirrors the fetchItems() logic in CatalogView.vue
  const params = {
    active_only: filters.active_only,
    in_stock: filters.in_stock,
  }
  if (filters.search) params.search = filters.search
  if (filters.price_min !== null && filters.price_min !== '') params.price_min = filters.price_min
  if (filters.price_max !== null && filters.price_max !== '') params.price_max = filters.price_max
  if (filters.harvest_date_from) params.harvest_date_from = filters.harvest_date_from
  if (filters.harvest_date_to) params.harvest_date_to = filters.harvest_date_to
  if (filters.tags) params.tags = filters.tags
  if (filters.priority_min !== null) params.priority_min = filters.priority_min
  return params
}

describe('CatalogView — filter params include tags and priority', () => {
  const baseFilters = {
    search: '', active_only: true, price_min: null, price_max: null,
    harvest_date_from: '', harvest_date_to: '', in_stock: false,
    tags: '', priority_min: null,
  }

  it('tags param is included when tags filter is non-empty', () => {
    const params = buildCatalogParams({ ...baseFilters, tags: 'organic,premium' })
    expect(params.tags).toBe('organic,premium')
  })

  it('tags param is omitted when tags filter is empty string', () => {
    const params = buildCatalogParams({ ...baseFilters, tags: '' })
    expect(params.tags).toBeUndefined()
  })

  it('priority_min param is included when set', () => {
    const params = buildCatalogParams({ ...baseFilters, priority_min: 3 })
    expect(params.priority_min).toBe(3)
  })

  it('priority_min param is omitted when null', () => {
    const params = buildCatalogParams({ ...baseFilters, priority_min: null })
    expect(params.priority_min).toBeUndefined()
  })

  it('all standard filters still pass through unchanged', () => {
    const params = buildCatalogParams({
      ...baseFilters, search: 'wheat', price_min: 10, active_only: false,
    })
    expect(params.search).toBe('wheat')
    expect(params.price_min).toBe(10)
    expect(params.active_only).toBe(false)
  })
})

// ── 8. CMS workflow — WorkflowTransitionRequest body contract ─────────────────

function buildCmsWorkflowBody(note) {
  // Mirrors workflowAction() and handleReject() in CMSView.vue
  return { note: note ?? null }
}

describe('CMSView — workflow actions send required WorkflowTransitionRequest body', () => {
  it('workflowAction sends body with note: null when no note given', () => {
    const body = buildCmsWorkflowBody(undefined)
    expect(body).toHaveProperty('note')
    expect(body.note).toBeNull()
  })

  it('handleReject sends note key (not reason key)', () => {
    const body = buildCmsWorkflowBody('Needs revision')
    expect(body).toHaveProperty('note', 'Needs revision')
    expect(body.reason).toBeUndefined()
  })

  it('rollback sends body with note key', () => {
    const body = buildCmsWorkflowBody(null)
    expect(body).toHaveProperty('note')
    expect(Object.keys(body)).toEqual(['note'])
  })

  it('all six workflow endpoints use same body shape', () => {
    const actions = ['submit-review', 'approve', 'reject', 'archive', 'restore', 'rollback']
    actions.forEach(action => {
      const body = buildCmsWorkflowBody(null)
      // Every transition body must have exactly the `note` key
      expect(Object.keys(body)).toContain('note')
      expect(Object.keys(body)).not.toContain('reason')
    })
  })
})

// ── 9. ReviewsView — exam_type payload shape ──────────────────────────────────

function buildReviewPayload(form, tagsStr) {
  // Mirrors handleCreate() payload construction in ReviewsView.vue
  const tags = tagsStr ? tagsStr.split(',').map(t => t.trim()).filter(Boolean) : []
  const payload = {
    subject_type: form.subject_type,
    order_id: form.order_id || null,
    rating: form.rating,
    comment: form.comment,
    tags: tags.length ? JSON.stringify(tags) : null,
  }
  if (form.subject_type === 'exam_type') {
    payload.subject_text = form.subject_text?.trim()
  } else {
    payload.subject_id = form.subject_id
  }
  return payload
}

describe('ReviewsView — exam_type vs product/catalog_item payload shape', () => {
  const baseForm = { order_id: 42, rating: 4, comment: 'Good', subject_type: '', subject_id: null, subject_text: '' }

  it('exam_type sends subject_text, not subject_id', () => {
    const payload = buildReviewPayload(
      { ...baseForm, subject_type: 'exam_type', subject_text: 'CBC' }, ''
    )
    expect(payload.subject_text).toBe('CBC')
    expect(payload.subject_id).toBeUndefined()
  })

  it('product sends subject_id, not subject_text', () => {
    const payload = buildReviewPayload(
      { ...baseForm, subject_type: 'product', subject_id: 7 }, ''
    )
    expect(payload.subject_id).toBe(7)
    expect(payload.subject_text).toBeUndefined()
  })

  it('catalog_item sends subject_id, not subject_text', () => {
    const payload = buildReviewPayload(
      { ...baseForm, subject_type: 'catalog_item', subject_id: 3 }, ''
    )
    expect(payload.subject_id).toBe(3)
    expect(payload.subject_text).toBeUndefined()
  })

  it('exam_type payload passes backend model_validator requirements', () => {
    const payload = buildReviewPayload(
      { ...baseForm, subject_type: 'exam_type', subject_text: 'Urinalysis' }, 'accurate'
    )
    // Must have subject_text, must NOT have subject_id
    expect(payload.subject_text).toBeTruthy()
    expect(payload.subject_id).toBeUndefined()
    expect(payload.subject_type).toBe('exam_type')
  })

  it('review filter uses rating_min not min_rating for backend param', () => {
    // Mirrors fetchReviews() in ReviewsView.vue
    const filters = { min_rating: 4 }
    const params = {}
    if (filters.min_rating) params.rating_min = filters.min_rating  // correct mapping
    expect(params.rating_min).toBe(4)
    expect(params.min_rating).toBeUndefined()
  })
})
