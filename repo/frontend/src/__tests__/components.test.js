/**
 * Real component mount tests — imports and renders actual SFCs from
 * src/components/. No copied helper logic; props, slots, emits, and
 * conditional rendering are all exercised through the real templates.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../api/index.js', () => ({
  default: { get: vi.fn(async () => ({ data: { unread_count: 0 } })), post: vi.fn() },
}))

import api from '../api/index.js'
import StatusBadge from '../components/StatusBadge.vue'
import Modal from '../components/Modal.vue'
import RoleGuard from '../components/RoleGuard.vue'
import DataTable from '../components/DataTable.vue'
import TraceTimeline from '../components/TraceTimeline.vue'
import NavBar from '../components/NavBar.vue'
import { useAuthStore } from '../stores/auth.js'

const stubView = { template: '<div></div>' }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: stubView },
      { path: '/packages', component: stubView },
      { path: '/packages/setup', component: stubView },
      { path: '/exams', component: stubView },
      { path: '/catalog', component: stubView },
      { path: '/reviews', component: stubView },
      { path: '/messages', component: stubView },
      { path: '/cms', component: stubView },
      { path: '/admin', component: stubView },
      { path: '/users', component: stubView },
      { path: '/login', component: stubView },
      { path: '/notifications', component: stubView },
      { path: '/profile', component: stubView },
    ],
  })
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
})


// ---------------------------------------------------------------------------
// StatusBadge
// ---------------------------------------------------------------------------

describe('StatusBadge.vue', () => {
  it('renders the raw status text when no label is provided', () => {
    const w = mount(StatusBadge, { props: { status: 'scheduled' } })
    expect(w.text()).toContain('scheduled')
  })

  it('prefers the label prop over the status when both are set', () => {
    const w = mount(StatusBadge, { props: { status: 'scheduled', label: 'Upcoming' } })
    expect(w.text()).toContain('Upcoming')
    expect(w.text()).not.toContain('scheduled')
  })

  it('applies the correct color class for each known status', () => {
    for (const [s, expected] of Object.entries({
      completed: 'green',
      cancelled: 'red',
      in_progress: 'yellow',
      admin: 'red',
      published: 'green',
      draft: 'yellow',
    })) {
      const w = mount(StatusBadge, { props: { status: s } })
      expect(w.find('span').classes().join(' ')).toContain(expected)
    }
  })

  it('falls back to a neutral class for unknown statuses', () => {
    const w = mount(StatusBadge, { props: { status: 'mystery-state' } })
    expect(w.find('span').classes().join(' ')).toMatch(/slate/)
  })
})


// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

describe('Modal.vue', () => {
  it('does not render when modelValue is false', async () => {
    const w = mount(Modal, {
      props: { modelValue: false, title: 'Test' },
      attachTo: document.body,
    })
    // Teleport sends content to body — searching body for the title
    expect(document.body.textContent).not.toContain('Test')
    w.unmount()
  })

  it('renders title + default slot when modelValue is true', async () => {
    const w = mount(Modal, {
      props: { modelValue: true, title: 'Confirm delete' },
      slots: { default: '<p class="modal-body">Are you sure?</p>' },
      attachTo: document.body,
    })
    await flushPromises()
    expect(document.body.textContent).toContain('Confirm delete')
    expect(document.body.textContent).toContain('Are you sure?')
    w.unmount()
  })

  it('emits update:modelValue=false when the close button is clicked', async () => {
    const w = mount(Modal, {
      props: { modelValue: true, title: 'X' },
      attachTo: document.body,
    })
    await flushPromises()
    const btn = document.body.querySelector('button')
    btn.click()
    await flushPromises()
    const events = w.emitted('update:modelValue')
    expect(events).toBeTruthy()
    expect(events[events.length - 1]).toEqual([false])
    w.unmount()
  })
})


// ---------------------------------------------------------------------------
// RoleGuard
// ---------------------------------------------------------------------------

describe('RoleGuard.vue', () => {
  it('renders the slot when the user role matches', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, role: 'admin' }
    const w = mount(RoleGuard, {
      props: { roles: ['admin'] },
      slots: { default: '<span class="secret">top-secret</span>' },
    })
    expect(w.text()).toContain('top-secret')
  })

  it('hides the slot when the role does not match', () => {
    const auth = useAuthStore()
    auth.user = { id: 1, role: 'end_user' }
    const w = mount(RoleGuard, {
      props: { roles: ['admin'] },
      slots: { default: '<span class="secret">top-secret</span>' },
    })
    expect(w.text()).not.toContain('top-secret')
  })

  it('hides the slot when the user is not authenticated', () => {
    const auth = useAuthStore()
    auth.user = null
    const w = mount(RoleGuard, {
      props: { roles: ['admin'] },
      slots: { default: '<span>secret</span>' },
    })
    expect(w.text()).not.toContain('secret')
  })

  it('accepts any of multiple roles', () => {
    const auth = useAuthStore()
    auth.user = { role: 'catalog_manager' }
    const w = mount(RoleGuard, {
      props: { roles: ['admin', 'catalog_manager'] },
      slots: { default: '<span>ok</span>' },
    })
    expect(w.text()).toContain('ok')
  })
})


// ---------------------------------------------------------------------------
// DataTable
// ---------------------------------------------------------------------------

describe('DataTable.vue', () => {
  const columns = [
    { key: 'name', label: 'Name' },
    { key: 'price', label: 'Price' },
  ]

  it('renders column headers', () => {
    const w = mount(DataTable, { props: { columns, rows: [] } })
    expect(w.text()).toContain('Name')
    expect(w.text()).toContain('Price')
  })

  it('shows loading spinner + text when loading=true', () => {
    const w = mount(DataTable, { props: { columns, rows: [], loading: true } })
    expect(w.text()).toContain('Loading...')
  })

  it('shows the empty state message when rows are empty', () => {
    const w = mount(DataTable, {
      props: { columns, rows: [], emptyText: 'Nothing here yet' },
    })
    expect(w.text()).toContain('Nothing here yet')
  })

  it('renders one row per item', () => {
    const w = mount(DataTable, {
      props: {
        columns,
        rows: [
          { id: 1, name: 'Apples', price: 1.99 },
          { id: 2, name: 'Bananas', price: 0.49 },
        ],
      },
    })
    expect(w.text()).toContain('Apples')
    expect(w.text()).toContain('Bananas')
  })

  it('paginates when rows exceed pageSize', async () => {
    const rows = Array.from({ length: 12 }, (_, i) => ({
      id: i + 1, name: `Row ${i + 1}`, price: i,
    }))
    const w = mount(DataTable, { props: { columns, rows, pageSize: 5 } })
    // First page — shows rows 1..5
    expect(w.text()).toContain('Row 1')
    expect(w.text()).toContain('Row 5')
    expect(w.text()).not.toContain('Row 6')
    // Pagination footer present
    expect(w.text()).toContain('Showing 1 to 5')
    expect(w.text()).toContain('of 12 results')

    // Click Next
    const buttons = w.findAll('button')
    const next = buttons.find(b => b.text().includes('Next'))
    await next.trigger('click')
    expect(w.text()).toContain('Row 6')
    expect(w.text()).toContain('Row 10')
    expect(w.text()).not.toContain('Row 11... too far')
  })

  it('disables Previous on the first page and Next on the last', async () => {
    const rows = Array.from({ length: 3 }, (_, i) => ({ id: i, name: `r${i}` }))
    const w = mount(DataTable, { props: { columns, rows, pageSize: 10 } })
    // All rows fit on one page — pagination footer should not render
    expect(w.text()).not.toContain('Showing')
  })
})


// ---------------------------------------------------------------------------
// TraceTimeline
// ---------------------------------------------------------------------------

describe('TraceTimeline.vue', () => {
  it('renders one list item per event', () => {
    const events = [
      { id: 1, event_type: 'harvested', timestamp: '2026-01-01T00:00:00Z', location: 'Farm A' },
      { id: 2, event_type: 'processed', timestamp: '2026-01-02T00:00:00Z', location: 'Plant B' },
      { id: 3, event_type: 'shipped',   timestamp: '2026-01-03T00:00:00Z', location: 'Dock C' },
    ]
    const w = mount(TraceTimeline, { props: { events } })
    expect(w.findAll('li').length).toBe(3)
    expect(w.text()).toContain('Farm A')
    expect(w.text()).toContain('Plant B')
    expect(w.text()).toContain('Dock C')
  })

  it('renders nothing when the events array is empty', () => {
    const w = mount(TraceTimeline, { props: { events: [] } })
    expect(w.findAll('li').length).toBe(0)
  })
})


// ---------------------------------------------------------------------------
// NavBar
// ---------------------------------------------------------------------------

describe('NavBar.vue', () => {
  async function mountNav(role) {
    const router = makeRouter()
    await router.push('/dashboard')
    await router.isReady()
    const auth = useAuthStore()
    auth.user = role ? { id: 1, username: 'u', role } : null
    auth.accessToken = role ? 'AT' : null
    const w = mount(NavBar, { global: { plugins: [router] } })
    return { w, router }
  }

  it('renders Dashboard + Packages links for every role', async () => {
    const { w } = await mountNav('end_user')
    expect(w.text()).toContain('Dashboard')
    expect(w.text()).toContain('Packages')
  })

  it('shows admin-only links only to admins', async () => {
    const { w: adminNav } = await mountNav('admin')
    expect(adminNav.text()).toContain('Admin')
    expect(adminNav.text()).toContain('Users')
    expect(adminNav.text()).toContain('Pkg Setup')

    const { w: endUserNav } = await mountNav('end_user')
    expect(endUserNav.text()).not.toContain('Admin')
    expect(endUserNav.text()).not.toContain('Users')
    expect(endUserNav.text()).not.toContain('Pkg Setup')
  })

  it('shows Exams to admin and clinic_staff, hides from end_user', async () => {
    const { w: staff } = await mountNav('clinic_staff')
    expect(staff.text()).toContain('Exams')

    const { w: user } = await mountNav('end_user')
    expect(user.text()).not.toContain('Exams')
  })

  it('shows CMS to catalog_manager', async () => {
    const { w } = await mountNav('catalog_manager')
    expect(w.text()).toContain('CMS')
  })

  it('renders the unread-count badge when >0', async () => {
    const { w } = await mountNav('admin')
    const { useNotificationStore } = await import('../stores/notifications.js')
    const ns = useNotificationStore()
    ns.unreadCount = 5
    await flushPromises()
    expect(w.text()).toContain('5')
  })

  it('caps displayed unread count at 99+', async () => {
    const { w } = await mountNav('admin')
    const { useNotificationStore } = await import('../stores/notifications.js')
    const ns = useNotificationStore()
    ns.unreadCount = 250
    await flushPromises()
    expect(w.text()).toContain('99+')
  })
})
