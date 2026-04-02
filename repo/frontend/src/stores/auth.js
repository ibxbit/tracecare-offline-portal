import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/index.js'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token') || null)
  const refreshToken = ref(localStorage.getItem('refresh_token') || null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const userRole = computed(() => user.value?.role || null)

  function isRole(...roles) {
    return roles.includes(userRole.value)
  }

  /** Scope per-user stores after the user record is populated. */
  function _scopeUserStores() {
    if (!user.value) return
    const uid = String(user.value.id)
    // Dynamic imports break circular-dependency cycles at call time.
    import('./quickviews.js').then(({ useQuickViewStore }) => {
      useQuickViewStore().init(uid)
    }).catch(() => {})
    import('./offline.js').then(({ useOfflineStore }) => {
      useOfflineStore().init(uid)
    }).catch(() => {})
  }

  async function login(username, password) {
    const response = await api.post('/auth/login', { username, password })
    const { access_token, refresh_token } = response.data
    accessToken.value = access_token
    refreshToken.value = refresh_token
    localStorage.setItem('access_token', access_token)
    localStorage.setItem('refresh_token', refresh_token)
    await fetchUser()
    _scopeUserStores()
  }

  async function logout() {
    // Wipe user-scoped cached data before destroying the session.
    try {
      const { useQuickViewStore } = await import('./quickviews.js')
      useQuickViewStore().clear()
    } catch { /* store not yet initialised */ }
    try {
      const { useOfflineStore } = await import('./offline.js')
      useOfflineStore().cacheClearAll()
    } catch { /* store not yet initialised */ }

    try {
      if (refreshToken.value) {
        await api.post('/auth/logout', { refresh_token: refreshToken.value })
      }
    } catch {
      // Proceed with local logout even if server call fails
    } finally {
      accessToken.value = null
      refreshToken.value = null
      user.value = null
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    }
  }

  async function fetchUser() {
    try {
      const response = await api.get('/users/me')
      user.value = response.data
    } catch {
      user.value = null
    }
  }

  async function refreshTokens() {
    if (!refreshToken.value) return false
    try {
      const response = await api.post('/auth/refresh', {
        refresh_token: refreshToken.value,
      })
      const { access_token, refresh_token } = response.data
      accessToken.value = access_token
      refreshToken.value = refresh_token
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      return true
    } catch {
      return false
    }
  }

  async function init() {
    if (accessToken.value) {
      await fetchUser()
      _scopeUserStores()
    }
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    userRole,
    isRole,
    login,
    logout,
    fetchUser,
    refreshTokens,
    init,
  }
})
