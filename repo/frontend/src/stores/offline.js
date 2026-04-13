import { defineStore } from 'pinia'
import { ref } from 'vue'

const BASE_PREFIX = 'tc_cache_'
const DEFAULT_TTL_MS = 5 * 60 * 1000  // 5 minutes

export const useOfflineStore = defineStore('offline', () => {
  const isOnline = ref(navigator.onLine)
  // Scoped per user so a new login never reads another user's cached data.
  const _userId = ref('anon')

  window.addEventListener('online',  () => { isOnline.value = true  })
  window.addEventListener('offline', () => { isOnline.value = false })

  function _prefix() {
    return `${BASE_PREFIX}${_userId.value}_`
  }

  /**
   * Scope the cache to an authenticated user.
   * Called by auth store after login/init.
   */
  function init(userId) {
    _userId.value = String(userId)
  }

  function cacheSet(key, data, ttlMs = DEFAULT_TTL_MS) {
    try {
      localStorage.setItem(_prefix() + key, JSON.stringify({
        data, expiresAt: Date.now() + ttlMs,
      }))
    } catch { /* storage full — ignore */ }
  }

  function cacheGet(key) {
    try {
      const raw = localStorage.getItem(_prefix() + key)
      if (!raw) return null
      const { data, expiresAt } = JSON.parse(raw)
      if (Date.now() > expiresAt) { localStorage.removeItem(_prefix() + key); return null }
      return data
    } catch { return null }
  }

  function cacheClear(key) {
    localStorage.removeItem(_prefix() + key)
  }

  /** Clear all cache entries for the current user and reset to anonymous scope. */
  function cacheClearAll() {
    const prefix = _prefix()
    Object.keys(localStorage)
      .filter(k => k.startsWith(prefix))
      .forEach(k => localStorage.removeItem(k))
    _userId.value = 'anon'
    // Remove any keys for the previous user after switching to anon
    const anonPrefix = _prefix()
    Object.keys(localStorage)
      .filter(k => k.startsWith(anonPrefix))
      .forEach(k => localStorage.removeItem(k))
  }

  /** Fetch with automatic offline fallback to cache. */
  async function fetchWithCache(key, fetcher, ttlMs = DEFAULT_TTL_MS) {
    if (isOnline.value) {
      try {
        const data = await fetcher()
        cacheSet(key, data, ttlMs)
        return { data, fromCache: false }
      } catch (err) {
        const cached = cacheGet(key)
        if (cached) return { data: cached, fromCache: true }
        throw err
      }
    } else {
      const cached = cacheGet(key)
      if (cached) return { data: cached, fromCache: true }
      throw new Error('Offline and no cached data available')
    }
  }

  return { isOnline, init, cacheSet, cacheGet, cacheClear, cacheClearAll, fetchWithCache }
})
