/**
 * F-4 — Logout / user-switch isolation tests.
 *
 * Verifies that:
 *   - Quick-views are scoped per user (different storage keys)
 *   - Offline cache is scoped per user
 *   - After logout/clear, no prior user's data leaks to the next session
 *   - init(userId) re-loads from the correct user-scoped key
 */
import { describe, it, expect, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useQuickViewStore } from '../stores/quickviews.js'
import { useOfflineStore } from '../stores/offline.js'

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
})

// ── QuickView store isolation ─────────────────────────────────────────────────

describe('useQuickViewStore — user isolation', () => {
  it('init(userId) scopes the storage key to that user', () => {
    const store = useQuickViewStore()
    store.init('42')
    store.add({ id: 1, type: 'package', label: 'Pkg A', route: '/packages/1' })
    expect(localStorage.getItem('tc_quick_views_42')).not.toBeNull()
    expect(localStorage.getItem('tc_quick_views_99')).toBeNull()
  })

  it('two users have independent view lists', () => {
    const storeA = useQuickViewStore()
    storeA.init('1')
    storeA.add({ id: 10, type: 'package', label: 'A-pkg', route: '/packages/10' })

    const storeB = useQuickViewStore()
    storeB.init('2')
    // User 2 should NOT see user 1's items
    expect(storeB.isSaved(10, 'package')).toBe(false)
    storeB.add({ id: 20, type: 'catalog', label: 'B-cat', route: '/catalog/20' })

    // Switch back to user 1 — their item is still there
    storeA.init('1')
    expect(storeA.isSaved(10, 'package')).toBe(true)
    expect(storeA.isSaved(20, 'catalog')).toBe(false)
  })

  it('clear() removes the current user key from localStorage and resets to anon', () => {
    const store = useQuickViewStore()
    store.init('7')
    store.add({ id: 5, type: 'review', label: 'R', route: '/reviews/5' })
    expect(store.views.length).toBe(1)
    store.clear()
    expect(store.views.length).toBe(0)
    expect(localStorage.getItem('tc_quick_views_7')).toBeNull()
  })

  it('after clear(), a new init loads a fresh empty list for the next user', () => {
    const store = useQuickViewStore()
    store.init('3')
    store.add({ id: 99, type: 'package', label: 'X', route: '/packages/99' })
    store.clear()       // logout

    store.init('4')     // next user logs in
    expect(store.views.length).toBe(0)
    expect(store.isSaved(99, 'package')).toBe(false)
  })

  it('MAX_QUICK_VIEWS is enforced per user', () => {
    const store = useQuickViewStore()
    store.init('5')
    for (let i = 0; i < 21; i++) {
      store.add({ id: i, type: 'package', label: `P${i}`, route: `/packages/${i}` })
    }
    expect(store.views.length).toBe(20)
    const res = store.add({ id: 999, type: 'package', label: 'overflow', route: '/packages/999' })
    expect(res.added).toBe(false)
  })
})

// ── Offline store isolation ───────────────────────────────────────────────────

describe('useOfflineStore — user isolation', () => {
  it('init(userId) prefixes cache keys with user id', () => {
    const store = useOfflineStore()
    store.init('42')
    store.cacheSet('catalog_list', [{ id: 1 }])
    expect(localStorage.getItem('tc_cache_42_catalog_list')).not.toBeNull()
    expect(localStorage.getItem('tc_cache_anon_catalog_list')).toBeNull()
  })

  it('user A cannot read user B cache entries', () => {
    const store = useOfflineStore()
    store.init('1')
    store.cacheSet('my_data', { secret: 'user1' })

    store.init('2')
    const result = store.cacheGet('my_data')
    expect(result).toBeNull()
  })

  it('cacheClearAll() only removes current user keys', () => {
    const store = useOfflineStore()
    store.init('10')
    store.cacheSet('k1', 'data10')

    store.init('20')
    store.cacheSet('k1', 'data20')

    store.init('10')
    store.cacheClearAll()                       // logout user 10

    // User 20's data should be untouched
    store.init('20')
    expect(store.cacheGet('k1')).toBe('data20')
  })

  it('cacheClearAll() resets userId to anon', () => {
    const store = useOfflineStore()
    store.init('99')
    store.cacheSet('x', 'v')
    store.cacheClearAll()

    // Should now operate under 'anon' prefix — user-99 key is gone
    expect(localStorage.getItem('tc_cache_99_x')).toBeNull()
  })

  it('cacheGet returns null for expired entries', () => {
    const store = useOfflineStore()
    store.init('5')
    store.cacheSet('expired_key', 'old data', -1)   // TTL -1 ms = already expired
    expect(store.cacheGet('expired_key')).toBeNull()
  })
})
