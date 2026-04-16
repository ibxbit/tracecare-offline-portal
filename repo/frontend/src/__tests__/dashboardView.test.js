/**
 * Real Vue component mount test for src/views/DashboardView.vue.
 *
 * The dashboard renders role-gated panels and queries several APIs on mount.
 * This test mounts the REAL SFC and asserts:
 *   - it renders the greeting with the logged-in username
 *   - role-gated sections appear/disappear based on userRole
 *   - a network failure doesn't crash the render
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../api/index.js', () => ({
  default: {
    get: vi.fn(async () => ({ data: [] })),
    post: vi.fn(),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../api/index.js'
import DashboardView from '../views/DashboardView.vue'
import { useAuthStore } from '../stores/auth.js'

const stub = { template: '<div></div>' }

async function mountDashboard(user) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', redirect: '/dashboard' },
      { path: '/dashboard', component: DashboardView },
      { path: '/exams', component: stub },
      { path: '/packages', component: stub },
      { path: '/catalog', component: stub },
      { path: '/cms', component: stub },
      { path: '/admin', component: stub },
      { path: '/notifications', component: stub },
    ],
  })
  await router.push('/dashboard')
  await router.isReady()

  // Seed the auth store directly — no HTTP call needed.
  const authStore = useAuthStore()
  authStore.user = user
  authStore.accessToken = 'AT'

  const wrapper = mount(DashboardView, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return { wrapper, router }
}


beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
  api.get.mockResolvedValue({ data: [] })
})


describe('DashboardView.vue — rendered component', () => {
  it('greets the logged-in admin by username', async () => {
    const { wrapper } = await mountDashboard({
      id: 1, username: 'admin', role: 'admin',
    })
    expect(wrapper.text()).toContain('admin')
    expect(wrapper.text()).toContain('Dashboard')
  })

  it('shows the staff-only panel when user is clinic_staff', async () => {
    const { wrapper } = await mountDashboard({
      id: 2, username: 'nurse', role: 'clinic_staff',
    })
    expect(wrapper.text()).toContain('Recent Exams')
  })

  it('hides staff panels from end_user', async () => {
    const { wrapper } = await mountDashboard({
      id: 3, username: 'patient', role: 'end_user',
    })
    expect(wrapper.text()).not.toContain('Recent Exams')
  })

  it('does not crash when the dashboard API calls fail (offline)', async () => {
    api.get.mockRejectedValue(new Error('offline'))
    const { wrapper } = await mountDashboard({
      id: 1, username: 'admin', role: 'admin',
    })
    // Still mounted, still has the heading
    expect(wrapper.text()).toContain('Dashboard')
  })
})
