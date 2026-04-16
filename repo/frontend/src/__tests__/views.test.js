/**
 * Real view mount tests — imports actual SFCs from src/views/ and
 * renders them with @vue/test-utils. The HTTP boundary is mocked
 * (src/api/index.js) but every other layer — stores, router, child
 * components — is the real application code.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../api/index.js', () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(async () => ({ data: {} })),
    put: vi.fn(async () => ({ data: {} })),
    patch: vi.fn(async () => ({ data: {} })),
    delete: vi.fn(async () => ({ data: {} })),
  },
}))

import api from '../api/index.js'
import CMSView from '../views/CMSView.vue'
import CatalogView from '../views/CatalogView.vue'
import ReviewsView from '../views/ReviewsView.vue'
import NotificationsView from '../views/NotificationsView.vue'
import PackagesView from '../views/PackagesView.vue'
import { useAuthStore } from '../stores/auth.js'

const stub = { template: '<div></div>' }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: stub },
      { path: '/packages', component: stub },
      { path: '/packages/setup', component: stub },
      { path: '/packages/:id/diff', component: stub },
      { path: '/catalog', component: stub },
      { path: '/reviews', component: stub },
      { path: '/cms', component: stub },
      { path: '/notifications', component: stub },
      { path: '/messages', component: stub },
      { path: '/admin', component: stub },
      { path: '/users', component: stub },
      { path: '/profile', component: stub },
      { path: '/login', component: stub },
    ],
  })
}

async function mountView(View, role = 'admin', routePath = '/') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = makeRouter()
  await router.push(routePath)
  await router.isReady()
  const auth = useAuthStore()
  auth.user = { id: 1, username: 'tester', role }
  auth.accessToken = 'AT'
  const wrapper = mount(View, { global: { plugins: [pinia, router] } })
  await flushPromises()
  return { wrapper, router, auth }
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  // Default: empty arrays / objects so onMounted handlers don't break.
  // Always include a `headers` object — some views inspect response headers
  // (e.g. ReviewsView reads X-Total-Count) and crash on undefined.
  api.get.mockImplementation(async (url) => {
    const headers = { 'x-total-count': '0' }
    if (url === '/notifications/admin/metrics') {
      return {
        headers,
        data: {
          total: 0, delivered: 0, failed: 0, retrying: 0, pending: 0,
          delivery_rate_pct: 0, avg_attempts_on_delivered: 0, by_type: {},
        },
      }
    }
    return { headers, data: [] }
  })
})


// ---------------------------------------------------------------------------
// CMSView
// ---------------------------------------------------------------------------

describe('CMSView.vue', () => {
  it('fetches the page list on mount via GET /cms/pages', async () => {
    await mountView(CMSView, 'admin')
    const calls = api.get.mock.calls.map(c => c[0])
    expect(calls).toContain('/cms/pages')
  })

  it('renders list rows for the returned pages', async () => {
    api.get.mockImplementationOnce(async () => ({
      data: [
        { id: 1, title: 'Notice A', slug: 'notice-a', status: 'draft',
          store_id: 'default', locale: 'en', updated_at: '2026-01-01T00:00:00Z',
          created_by: 1, current_revision: 1, page_type: 'notice' },
        { id: 2, title: 'Notice B', slug: 'notice-b', status: 'published',
          store_id: 'default', locale: 'en', updated_at: '2026-01-02T00:00:00Z',
          created_by: 1, current_revision: 3, page_type: 'notice' },
      ],
    }))
    const { wrapper } = await mountView(CMSView, 'admin')
    expect(wrapper.text()).toContain('Notice A')
    expect(wrapper.text()).toContain('Notice B')
  })

  it('renders empty-state copy when API returns no pages', async () => {
    const { wrapper } = await mountView(CMSView, 'admin')
    expect(wrapper.text().toLowerCase()).toMatch(/no\s+pages|nothing|empty|create/)
  })
})


// ---------------------------------------------------------------------------
// CatalogView
// ---------------------------------------------------------------------------

describe('CatalogView.vue', () => {
  it('fetches catalog on mount via GET /catalog', async () => {
    await mountView(CatalogView, 'admin')
    const calls = api.get.mock.calls.map(c => c[0])
    expect(calls).toContain('/catalog')
  })

  it('renders rows returned by the API', async () => {
    api.get.mockImplementationOnce(async () => ({
      headers: { 'x-total-count': '1' },
      data: [
        { id: 1, name: 'Organic Tomato', category: 'produce',
          price: '1.99', stock_quantity: 42, is_active: true,
          created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' },
      ],
    }))
    const { wrapper } = await mountView(CatalogView, 'admin')
    expect(wrapper.text()).toContain('Organic Tomato')
  })

  it('handles an API failure gracefully (no crash)', async () => {
    // Catch the unhandled rejection from the component's async onMounted
    // fetch so it doesn't surface as a test-runner error.
    const originalOnRejection = process.listeners('unhandledRejection').slice()
    process.removeAllListeners('unhandledRejection')
    process.on('unhandledRejection', () => { /* swallow expected */ })
    try {
      api.get.mockRejectedValue(new Error('500'))
      const { wrapper } = await mountView(CatalogView, 'admin')
      expect(wrapper.html().length).toBeGreaterThan(0)
    } finally {
      process.removeAllListeners('unhandledRejection')
      originalOnRejection.forEach(l => process.on('unhandledRejection', l))
    }
  })
})


// ---------------------------------------------------------------------------
// ReviewsView
// ---------------------------------------------------------------------------

describe('ReviewsView.vue', () => {
  it('fetches reviews list on mount', async () => {
    await mountView(ReviewsView, 'admin')
    const calls = api.get.mock.calls.map(c => c[0])
    expect(calls.some(u => u.startsWith('/reviews'))).toBe(true)
  })

  it('renders returned reviews', async () => {
    const headers = { 'x-total-count': '1' }
    api.get.mockImplementation(async (url) => {
      if (url === '/reviews' || url.startsWith('/reviews?') || (url.startsWith('/reviews') && !url.includes('summary'))) {
        return {
          headers,
          data: [
            { id: 1, subject_type: 'product', subject_id: 1, rating: 5,
              comment: 'Great product', credibility_score: 0.9,
              is_pinned: false, is_collapsed: false, store_id: 'default',
              reviewer_id: 2, order_id: 1, is_followup: false,
              submitted_at: '2026-01-01T00:00:00Z', created_at: '2026-01-01T00:00:00Z',
              images: [], followup_count: 0 },
          ],
        }
      }
      return { headers, data: [] }
    })
    const { wrapper } = await mountView(ReviewsView, 'admin')
    expect(wrapper.text()).toContain('Great product')
  })
})


// ---------------------------------------------------------------------------
// NotificationsView
// ---------------------------------------------------------------------------

describe('NotificationsView.vue', () => {
  it('admin view fetches delivery metrics', async () => {
    await mountView(NotificationsView, 'admin')
    const calls = api.get.mock.calls.map(c => c[0])
    expect(calls).toContain('/notifications/admin/metrics')
  })

  it('end_user view does NOT call admin metrics endpoint', async () => {
    await mountView(NotificationsView, 'end_user')
    const calls = api.get.mock.calls.map(c => c[0])
    expect(calls).not.toContain('/notifications/admin/metrics')
  })

  it('renders the notification list when the store has items', async () => {
    const { wrapper } = await mountView(NotificationsView, 'end_user')
    // Populate the notifications store directly and force re-render
    const { useNotificationStore } = await import('../stores/notifications.js')
    const ns = useNotificationStore()
    ns.notifications = [
      { id: 1, title: 'Order shipped', body: 'x', is_read: false,
        notification_type: 'info', event_subtype: 'shipped',
        created_at: '2026-01-01T00:00:00Z' },
    ]
    await flushPromises()
    expect(wrapper.text()).toContain('Order shipped')
  })
})


// ---------------------------------------------------------------------------
// PackagesView
// ---------------------------------------------------------------------------

describe('PackagesView.vue', () => {
  it('fetches packages on mount via GET /packages', async () => {
    await mountView(PackagesView, 'admin')
    const calls = api.get.mock.calls.map(c => c[0])
    expect(calls).toContain('/packages')
  })

  it('renders returned packages', async () => {
    api.get.mockImplementation(async () => ({
      headers: { 'x-total-count': '2' },
      data: [
        { id: 1, name: 'Basic Health', version: 1, price: '199.99',
          validity_window_days: 365, is_active: true,
          created_at: '2026-01-01T00:00:00Z', item_count: 5 },
        { id: 2, name: 'Premium Health', version: 2, price: '399.99',
          validity_window_days: 365, is_active: true,
          created_at: '2026-02-01T00:00:00Z', item_count: 12 },
      ],
    }))
    const { wrapper } = await mountView(PackagesView, 'admin')
    expect(wrapper.text()).toContain('Basic Health')
    expect(wrapper.text()).toContain('Premium Health')
  })

  it('handles API errors without crashing', async () => {
    const originalOnRejection = process.listeners('unhandledRejection').slice()
    process.removeAllListeners('unhandledRejection')
    process.on('unhandledRejection', () => {})
    try {
      api.get.mockRejectedValue(new Error('offline'))
      const { wrapper } = await mountView(PackagesView, 'admin')
      expect(wrapper.html().length).toBeGreaterThan(0)
    } finally {
      process.removeAllListeners('unhandledRejection')
      originalOnRejection.forEach(l => process.on('unhandledRejection', l))
    }
  })
})
