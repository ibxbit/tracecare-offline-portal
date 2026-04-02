import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/index.js'

export const useNotificationStore = defineStore('notifications', () => {
  const notifications = ref([])
  const unreadCount = ref(0)
  const preferences = ref(null)
  let pollInterval = null

  const unread = computed(() => notifications.value.filter(n => !n.is_read))

  async function fetchUnreadCount() {
    try {
      const res = await api.get('/notifications/unread-count')
      unreadCount.value = res.data.count ?? 0
    } catch { /* offline */ }
  }

  async function fetchNotifications(params = {}) {
    try {
      const res = await api.get('/notifications', { params })
      notifications.value = res.data
      unreadCount.value = res.data.filter(n => !n.is_read).length
    } catch { /* offline */ }
  }

  async function markRead(id) {
    await api.patch(`/notifications/${id}/read`)
    const n = notifications.value.find(n => n.id === id)
    if (n) { n.is_read = true; unreadCount.value = Math.max(0, unreadCount.value - 1) }
  }

  async function markAllRead() {
    await api.post('/notifications/mark-all-read')
    notifications.value.forEach(n => n.is_read = true)
    unreadCount.value = 0
  }

  async function deleteNotification(id) {
    await api.delete(`/notifications/${id}`)
    notifications.value = notifications.value.filter(n => n.id !== id)
  }

  async function fetchPreferences() {
    try {
      const res = await api.get('/notifications/preferences/me')
      preferences.value = res.data
    } catch { /* offline */ }
  }

  async function savePreferences(prefs) {
    const res = await api.put('/notifications/preferences/me', prefs)
    preferences.value = res.data
  }

  function startPolling(intervalMs = 30000) {
    fetchUnreadCount()
    pollInterval = setInterval(fetchUnreadCount, intervalMs)
  }

  function stopPolling() {
    if (pollInterval) { clearInterval(pollInterval); pollInterval = null }
  }

  return {
    notifications, unreadCount, preferences, unread,
    fetchUnreadCount, fetchNotifications, markRead, markAllRead,
    deleteNotification, fetchPreferences, savePreferences,
    startPolling, stopPolling,
  }
})
