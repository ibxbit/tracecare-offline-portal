import { defineStore } from 'pinia'
import { ref } from 'vue'

const BASE_KEY = 'tc_quick_views'
const MAX_QUICK_VIEWS = 20

export const useQuickViewStore = defineStore('quickviews', () => {
  // Current user key — 'anon' before login, user-id after.
  const _userKey = ref('anon')
  const views = ref(_load('anon'))

  function _storageKey(uid) {
    return `${BASE_KEY}_${uid}`
  }

  function _load(uid) {
    try {
      return JSON.parse(localStorage.getItem(_storageKey(uid)) || '[]')
    } catch { return [] }
  }

  function _save() {
    try {
      localStorage.setItem(_storageKey(_userKey.value), JSON.stringify(views.value))
    } catch { /* storage full */ }
  }

  /**
   * Scope quick-views to an authenticated user.
   * Called by auth store after login/init so each user sees only their own list.
   */
  function init(userId) {
    _userKey.value = String(userId)
    views.value = _load(_userKey.value)
  }

  function add(item) {
    const exists = views.value.find(v => v.id === item.id && v.type === item.type)
    if (exists) return { added: false, reason: 'Already saved' }
    if (views.value.length >= MAX_QUICK_VIEWS) {
      return { added: false, reason: `Maximum ${MAX_QUICK_VIEWS} quick views reached` }
    }
    views.value.unshift({ ...item, savedAt: new Date().toISOString() })
    _save()
    return { added: true }
  }

  function remove(id, type) {
    views.value = views.value.filter(v => !(v.id === id && v.type === type))
    _save()
  }

  function isSaved(id, type) {
    return views.value.some(v => v.id === id && v.type === type)
  }

  /** Clear this user's views from localStorage and reset to anonymous scope. */
  function clear() {
    views.value = []
    localStorage.removeItem(_storageKey(_userKey.value))
    _userKey.value = 'anon'
  }

  return { views, init, add, remove, isSaved, clear, MAX_QUICK_VIEWS }
})
