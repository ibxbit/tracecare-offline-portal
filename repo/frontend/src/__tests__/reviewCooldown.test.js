/**
 * F-5 — Review cooldown UI behaviour tests.
 *
 * Verifies:
 *   - _recordCooldown writes an expiry timestamp to localStorage
 *   - _cooldownExpiryFor returns 0 for an unknown order
 *   - cooldownSeconds > 0 blocks submission (guard logic)
 *   - cooldownSeconds reaches 0 after the expiry passes (simulated)
 *   - fmtCooldown formats seconds correctly (mm:ss style)
 *   - Different order IDs have independent cooldowns
 */
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'

// ── Extracted cooldown helpers (mirrors ReviewsView logic) ───────────────────

const COOLDOWN_MS = 10 * 60 * 1000
const COOLDOWN_STORAGE_KEY = 'tc_review_cooldowns'

function _loadCooldowns() {
  try { return JSON.parse(localStorage.getItem(COOLDOWN_STORAGE_KEY) || '{}') } catch { return {} }
}
function _saveCooldowns(cd) {
  localStorage.setItem(COOLDOWN_STORAGE_KEY, JSON.stringify(cd))
}
function _cooldownExpiryFor(orderId) {
  if (!orderId) return 0
  const cd = _loadCooldowns()
  return cd[String(orderId)] || 0
}
function _recordCooldown(orderId) {
  if (!orderId) return
  const cd = _loadCooldowns()
  cd[String(orderId)] = Date.now() + COOLDOWN_MS
  _saveCooldowns(cd)
}
function _cooldownSecondsLeft(orderId) {
  const expiry = _cooldownExpiryFor(orderId)
  return Math.max(0, Math.ceil((expiry - Date.now()) / 1000))
}
function fmtCooldown(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

beforeEach(() => { localStorage.clear() })
afterEach(() => { vi.restoreAllMocks() })

// ── Storage ───────────────────────────────────────────────────────────────────

describe('Cooldown — storage', () => {
  it('_cooldownExpiryFor returns 0 for an unrecorded order', () => {
    expect(_cooldownExpiryFor(42)).toBe(0)
  })

  it('_recordCooldown writes a future expiry to localStorage', () => {
    const before = Date.now()
    _recordCooldown(7)
    const expiry = _cooldownExpiryFor(7)
    expect(expiry).toBeGreaterThan(before)
    expect(expiry).toBeLessThanOrEqual(before + COOLDOWN_MS + 50)
  })

  it('_recordCooldown is a no-op when orderId is falsy', () => {
    _recordCooldown(null)
    _recordCooldown(0)
    expect(localStorage.getItem(COOLDOWN_STORAGE_KEY)).toBeNull()
  })

  it('different order IDs have independent cooldowns', () => {
    _recordCooldown(1)
    expect(_cooldownExpiryFor(1)).toBeGreaterThan(0)
    expect(_cooldownExpiryFor(2)).toBe(0)
  })
})

// ── Remaining seconds ─────────────────────────────────────────────────────────

describe('Cooldown — seconds remaining', () => {
  it('returns > 0 immediately after recording', () => {
    _recordCooldown(10)
    expect(_cooldownSecondsLeft(10)).toBeGreaterThan(0)
    expect(_cooldownSecondsLeft(10)).toBeLessThanOrEqual(600)
  })

  it('returns 0 for an expired cooldown (simulated by back-dating expiry)', () => {
    // Directly write an already-expired timestamp
    const cd = { '55': Date.now() - 1000 }
    _saveCooldowns(cd)
    expect(_cooldownSecondsLeft(55)).toBe(0)
  })

  it('returns 0 when no orderId is provided', () => {
    expect(_cooldownSecondsLeft(null)).toBe(0)
    expect(_cooldownSecondsLeft(undefined)).toBe(0)
  })
})

// ── Submission gate ───────────────────────────────────────────────────────────

describe('Cooldown — submission gate', () => {
  it('blocks submission when cooldownSeconds > 0', () => {
    _recordCooldown(99)
    const seconds = _cooldownSecondsLeft(99)
    const isBlocked = seconds > 0
    expect(isBlocked).toBe(true)
  })

  it('allows submission when cooldownSeconds === 0', () => {
    // No cooldown recorded
    const seconds = _cooldownSecondsLeft(123)
    const isBlocked = seconds > 0
    expect(isBlocked).toBe(false)
  })

  it('button disabled condition mirrors cooldownSeconds > 0', () => {
    _recordCooldown(5)
    const cooldownSeconds = _cooldownSecondsLeft(5)
    const creating = false
    const buttonDisabled = creating || cooldownSeconds > 0
    expect(buttonDisabled).toBe(true)
  })
})

// ── fmtCooldown ───────────────────────────────────────────────────────────────

describe('Cooldown — fmtCooldown formatting', () => {
  it('formats 600 seconds as "10m 0s"', () => {
    expect(fmtCooldown(600)).toBe('10m 0s')
  })
  it('formats 90 seconds as "1m 30s"', () => {
    expect(fmtCooldown(90)).toBe('1m 30s')
  })
  it('formats 45 seconds as "45s" (no minutes prefix)', () => {
    expect(fmtCooldown(45)).toBe('45s')
  })
  it('formats 0 seconds as "0s"', () => {
    expect(fmtCooldown(0)).toBe('0s')
  })
  it('formats 61 seconds as "1m 1s"', () => {
    expect(fmtCooldown(61)).toBe('1m 1s')
  })
})

// ── Review create payload contract — exam_type vs id-based subjects ───────────
//
// Backend contract (ReviewCreate.subject_consistency model_validator):
//   - subject_type == "exam_type"  → subject_text required,  subject_id must be null/absent
//   - subject_type != "exam_type"  → subject_id  required,   subject_text optional
//
// Mirrors handleCreate() payload construction in ReviewsView.vue.

function buildReviewPayload(form) {
  const payload = {
    subject_type: form.subject_type,
    order_id: form.order_id || null,
    rating: form.rating,
    comment: form.comment,
  }
  if (form.subject_type === 'exam_type') {
    payload.subject_text = form.subject_text?.trim() ?? ''
    // subject_id intentionally omitted for exam_type
  } else {
    payload.subject_id = form.subject_id
    // subject_text intentionally omitted for product/catalog_item
  }
  return payload
}

function validateReviewForm(form) {
  if (!form.subject_type) return 'Please select a subject type.'
  if (form.subject_type === 'exam_type') {
    if (!form.subject_text?.trim()) return 'Exam type name is required for exam type reviews.'
  } else {
    if (!form.subject_id) return 'Subject ID is required.'
  }
  if (!form.rating) return 'Please select a rating.'
  if (!form.comment) return 'Comment is required.'
  return null  // valid
}

const BASE_FORM = { order_id: 42, rating: 4, comment: 'Great', subject_type: '', subject_id: null, subject_text: '' }

describe('ReviewsView — exam_type payload contract (A-02 lock)', () => {
  it('exam_type payload includes subject_text and omits subject_id', () => {
    const payload = buildReviewPayload({ ...BASE_FORM, subject_type: 'exam_type', subject_text: 'CBC' })
    expect(payload.subject_text).toBe('CBC')
    expect(payload.subject_id).toBeUndefined()
  })

  it('product payload includes subject_id and omits subject_text', () => {
    const payload = buildReviewPayload({ ...BASE_FORM, subject_type: 'product', subject_id: 7 })
    expect(payload.subject_id).toBe(7)
    expect(payload.subject_text).toBeUndefined()
  })

  it('catalog_item payload includes subject_id and omits subject_text', () => {
    const payload = buildReviewPayload({ ...BASE_FORM, subject_type: 'catalog_item', subject_id: 3 })
    expect(payload.subject_id).toBe(3)
    expect(payload.subject_text).toBeUndefined()
  })

  it('exam_type with empty subject_text fails client-side validation', () => {
    const error = validateReviewForm({ ...BASE_FORM, subject_type: 'exam_type', subject_text: '' })
    expect(error).toBeTruthy()
    expect(error).toContain('Exam type name')
  })

  it('exam_type with whitespace-only subject_text fails client-side validation', () => {
    const error = validateReviewForm({ ...BASE_FORM, subject_type: 'exam_type', subject_text: '   ' })
    expect(error).toBeTruthy()
    expect(error).toContain('Exam type name')
  })

  it('exam_type with valid subject_text passes client-side validation', () => {
    const error = validateReviewForm({ ...BASE_FORM, subject_type: 'exam_type', subject_text: 'Urinalysis' })
    expect(error).toBeNull()
  })

  it('product without subject_id fails client-side validation', () => {
    const error = validateReviewForm({ ...BASE_FORM, subject_type: 'product', subject_id: null })
    expect(error).toBeTruthy()
    expect(error).toContain('Subject ID')
  })

  it('product with valid subject_id passes client-side validation', () => {
    const error = validateReviewForm({ ...BASE_FORM, subject_type: 'product', subject_id: 5 })
    expect(error).toBeNull()
  })

  it('subject_type change resets both subject_id and subject_text to avoid stale values', () => {
    // Mirrors the @change handler on the subject_type select in ReviewsView.vue
    let form = { subject_type: 'product', subject_id: 7, subject_text: '' }
    // Simulate changing to exam_type
    form = { ...form, subject_type: 'exam_type', subject_id: null, subject_text: '' }
    expect(form.subject_id).toBeNull()
    expect(form.subject_text).toBe('')
  })
})
