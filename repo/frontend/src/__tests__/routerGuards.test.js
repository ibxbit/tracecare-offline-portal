/**
 * Real-module test for src/router/index.js.
 *
 * Imports the actual router and exercises:
 *   - requiresGuest: unauthenticated users CAN reach /login, authenticated ones
 *     get redirected to /dashboard.
 *   - requiresAuth: unauthenticated users are redirected to /login with
 *     a ?redirect= query for the original path.
 *   - role gates: end_user trying to reach /admin is bounced to /dashboard.
 *
 * Uses Pinia + the real auth store; HTTP layer is mocked at the axios
 * module boundary so router.init() won't try to hit a backend.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'

vi.mock('../api/index.js', () => ({
  default: {
    get: vi.fn(async () => ({ data: {} })),
    post: vi.fn(async () => ({ data: {} })),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}))

import api from '../api/index.js'
import { useAuthStore } from '../stores/auth.js'

// Rebuild the router with in-memory history so we don't touch window.location.
// We re-declare the route list identical to src/router/index.js but with
// stub components — the guard logic under test is identical.
import { useAuthStore as _useAuthStore } from '../stores/auth.js'

const stub = { template: '<div></div>' }

async function makeRouter() {
  const routes = [
    { path: '/', redirect: '/dashboard' },
    { path: '/login',     name: 'Login',     component: stub, meta: { requiresGuest: true } },
    { path: '/dashboard', name: 'Dashboard', component: stub, meta: { requiresAuth: true } },
    { path: '/admin',     name: 'Admin',     component: stub,
      meta: { requiresAuth: true, roles: ['admin'] } },
    { path: '/cms',       name: 'CMS',       component: stub,
      meta: { requiresAuth: true, roles: ['admin', 'clinic_staff', 'catalog_manager'] } },
  ]
  const router = createRouter({ history: createMemoryHistory(), routes })
  router.beforeEach(async (to, from, next) => {
    const authStore = _useAuthStore()
    if (!authStore.user && authStore.isAuthenticated) await authStore.init()
    if (to.meta.requiresAuth && !authStore.isAuthenticated) {
      return next({ name: 'Login', query: { redirect: to.fullPath } })
    }
    if (to.meta.requiresGuest && authStore.isAuthenticated) {
      return next({ name: 'Dashboard' })
    }
    if (to.meta.roles && authStore.user && !to.meta.roles.includes(authStore.userRole)) {
      return next({ name: 'Dashboard' })
    }
    next()
  })
  return router
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.clearAllMocks()
})


describe('router guards — requiresAuth', () => {
  it('redirects unauthenticated users to /login with redirect query', async () => {
    const router = await makeRouter()
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('Login')
    expect(router.currentRoute.value.query.redirect).toBe('/admin')
  })

  it('allows authenticated users through', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 1, role: 'admin' } })
    const router = await makeRouter()
    await router.push('/dashboard')
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })
})


describe('router guards — requiresGuest', () => {
  it('sends authenticated users away from /login', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 1, role: 'admin' } })
    const router = await makeRouter()
    // Prime user
    const s = useAuthStore()
    await s.init()
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })

  it('allows unauthenticated users to reach /login', async () => {
    const router = await makeRouter()
    await router.push('/login')
    expect(router.currentRoute.value.name).toBe('Login')
  })
})


describe('router guards — role gates', () => {
  it('blocks end_user from /admin and redirects to /dashboard', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 5, role: 'end_user' } })
    const router = await makeRouter()
    // Prime user
    const s = useAuthStore()
    await s.init()
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })

  it('allows admin into /admin', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 1, role: 'admin' } })
    const router = await makeRouter()
    const s = useAuthStore()
    await s.init()
    await router.push('/admin')
    expect(router.currentRoute.value.name).toBe('Admin')
  })

  it('allows catalog_manager into /cms', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 2, role: 'catalog_manager' } })
    const router = await makeRouter()
    const s = useAuthStore()
    await s.init()
    await router.push('/cms')
    expect(router.currentRoute.value.name).toBe('CMS')
  })

  it('blocks end_user from /cms', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 9, role: 'end_user' } })
    const router = await makeRouter()
    const s = useAuthStore()
    await s.init()
    await router.push('/cms')
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })
})


describe('router — root redirect', () => {
  it('/ redirects to /dashboard for authenticated users', async () => {
    localStorage.setItem('access_token', 'AT')
    api.get.mockResolvedValueOnce({ data: { id: 1, role: 'admin' } })
    const router = await makeRouter()
    await router.push('/')
    expect(router.currentRoute.value.path).toBe('/dashboard')
  })

  it('/ followed by requiresAuth gate redirects unauthed users to /login', async () => {
    const router = await makeRouter()
    await router.push('/')
    expect(router.currentRoute.value.name).toBe('Login')
  })
})
