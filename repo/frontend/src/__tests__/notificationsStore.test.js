/**
 * Real-module test for src/stores/notifications.js.
 * Mocks only the HTTP boundary; exercises real store logic.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('../api/index.js', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../api/index.js'
import { useNotificationStore } from '../stores/notifications.js'

beforeEach(() => {
  setActivePinia(createPinia())
  vi.clearAllMocks()
})


describe('useNotificationStore — fetching', () => {
  it('fetchUnreadCount updates unreadCount', async () => {
    api.get.mockResolvedValueOnce({ data: { unread_count: 7 } })
    const s = useNotificationStore()
    await s.fetchUnreadCount()
    expect(s.unreadCount).toBe(7)
  })

  it('defaults unreadCount to 0 when response is malformed', async () => {
    api.get.mockResolvedValueOnce({ data: {} })
    const s = useNotificationStore()
    await s.fetchUnreadCount()
    expect(s.unreadCount).toBe(0)
  })

  it('silently swallows offline errors', async () => {
    api.get.mockRejectedValueOnce(new Error('offline'))
    const s = useNotificationStore()
    await expect(s.fetchUnreadCount()).resolves.toBeUndefined()
    expect(s.unreadCount).toBe(0)
  })

  it('fetchNotifications populates list + derives unread count from data', async () => {
    api.get.mockResolvedValueOnce({
      data: [
        { id: 1, title: 'a', is_read: false },
        { id: 2, title: 'b', is_read: true },
        { id: 3, title: 'c', is_read: false },
      ],
    })
    const s = useNotificationStore()
    await s.fetchNotifications({ limit: 50 })
    expect(s.notifications).toHaveLength(3)
    expect(s.unreadCount).toBe(2)
    expect(s.unread).toHaveLength(2)
    expect(s.unread.every(n => !n.is_read)).toBe(true)
  })
})


describe('useNotificationStore — mutations', () => {
  it('markRead flips is_read locally and decrements unreadCount', async () => {
    api.get.mockResolvedValueOnce({
      data: [{ id: 1, is_read: false }, { id: 2, is_read: false }],
    })
    api.patch.mockResolvedValueOnce({ data: {} })
    const s = useNotificationStore()
    await s.fetchNotifications()
    expect(s.unreadCount).toBe(2)

    await s.markRead(1)
    expect(api.patch).toHaveBeenCalledWith('/notifications/1/read')
    expect(s.notifications.find(n => n.id === 1).is_read).toBe(true)
    expect(s.unreadCount).toBe(1)
  })

  it('markRead does not drop unreadCount below 0', async () => {
    api.patch.mockResolvedValue({ data: {} })
    const s = useNotificationStore()
    s.notifications = [{ id: 1, is_read: false }]
    s.unreadCount = 0
    await s.markRead(1)
    expect(s.unreadCount).toBe(0)
  })

  it('markAllRead flips all + zeroes counter', async () => {
    api.post.mockResolvedValueOnce({ data: {} })
    const s = useNotificationStore()
    s.notifications = [
      { id: 1, is_read: false },
      { id: 2, is_read: false },
    ]
    s.unreadCount = 2
    await s.markAllRead()
    expect(api.post).toHaveBeenCalledWith('/notifications/mark-all-read')
    expect(s.notifications.every(n => n.is_read)).toBe(true)
    expect(s.unreadCount).toBe(0)
  })

  it('deleteNotification removes entry by id', async () => {
    api.delete.mockResolvedValueOnce({ data: {} })
    const s = useNotificationStore()
    s.notifications = [{ id: 1 }, { id: 2 }, { id: 3 }]
    await s.deleteNotification(2)
    expect(api.delete).toHaveBeenCalledWith('/notifications/2')
    expect(s.notifications.map(n => n.id)).toEqual([1, 3])
  })
})


describe('useNotificationStore — preferences', () => {
  it('fetchPreferences loads and stores prefs', async () => {
    api.get.mockResolvedValueOnce({
      data: { notify_order_accepted: true, notify_new_message: false },
    })
    const s = useNotificationStore()
    await s.fetchPreferences()
    expect(s.preferences.notify_order_accepted).toBe(true)
    expect(s.preferences.notify_new_message).toBe(false)
  })

  it('savePreferences PUTs and stores the server response', async () => {
    api.put.mockResolvedValueOnce({
      data: { notify_order_accepted: false },
    })
    const s = useNotificationStore()
    await s.savePreferences({ notify_order_accepted: false })
    expect(api.put).toHaveBeenCalledWith(
      '/notifications/preferences/me',
      { notify_order_accepted: false },
    )
    expect(s.preferences.notify_order_accepted).toBe(false)
  })
})


describe('useNotificationStore — polling', () => {
  it('startPolling kicks off an immediate fetch + sets an interval', async () => {
    vi.useFakeTimers()
    api.get.mockResolvedValue({ data: { unread_count: 1 } })
    const s = useNotificationStore()
    s.startPolling(10_000)
    await Promise.resolve() // allow the initial async fetch to resolve
    expect(api.get).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(10_000)
    await Promise.resolve()
    expect(api.get).toHaveBeenCalledTimes(2)

    s.stopPolling()
    vi.advanceTimersByTime(30_000)
    await Promise.resolve()
    expect(api.get).toHaveBeenCalledTimes(2)
    vi.useRealTimers()
  })
})
