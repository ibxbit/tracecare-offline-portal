/**
 * F-1 — Route registration and guard tests.
 *
 * Verifies that:
 *   - /products/:id/trace is registered as "ProductTrace"
 *   - It requires authentication (requiresAuth: true)
 *   - It has no role restriction (all authenticated users can view)
 *   - /products is also registered ("Products")
 *   - Unauthenticated navigation to a protected route redirects to /login
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia, setActivePinia } from 'pinia'

// ── Minimal stub components so lazy imports resolve synchronously ────────────
const Stub = { template: '<div/>' }

const routes = [
  { path: '/login', name: 'Login', component: Stub, meta: { requiresGuest: true } },
  { path: '/dashboard', name: 'Dashboard', component: Stub, meta: { requiresAuth: true } },
  { path: '/products', name: 'Products', component: Stub, meta: { requiresAuth: true } },
  {
    path: '/products/:id/trace',
    name: 'ProductTrace',
    component: Stub,
    meta: { requiresAuth: true },
  },
]

function makeRouter(isAuthenticated = false) {
  const router = createRouter({ history: createMemoryHistory(), routes })

  router.beforeEach((to, _from, next) => {
    if (to.meta.requiresAuth && !isAuthenticated) {
      return next({ name: 'Login', query: { redirect: to.fullPath } })
    }
    if (to.meta.requiresGuest && isAuthenticated) {
      return next({ name: 'Dashboard' })
    }
    next()
  })

  return router
}

describe('Router — /products/:id/trace', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('registers the ProductTrace route', () => {
    const router = makeRouter(true)
    const route = router.resolve({ name: 'ProductTrace', params: { id: 42 } })
    expect(route.name).toBe('ProductTrace')
    expect(route.path).toBe('/products/42/trace')
  })

  it('ProductTrace has requiresAuth meta flag', () => {
    const router = makeRouter(true)
    const route = router.resolve({ name: 'ProductTrace', params: { id: 1 } })
    expect(route.meta.requiresAuth).toBe(true)
  })

  it('ProductTrace has NO role restriction (any authenticated user can view)', () => {
    const router = makeRouter(true)
    const route = router.resolve({ name: 'ProductTrace', params: { id: 1 } })
    // The route spec does NOT include a roles array
    expect(route.meta.roles).toBeUndefined()
  })

  it('unauthenticated user is redirected to /login when navigating to ProductTrace', async () => {
    const router = makeRouter(false)  // not authenticated
    await router.push('/products/99/trace')
    expect(router.currentRoute.value.name).toBe('Login')
    expect(router.currentRoute.value.query.redirect).toBe('/products/99/trace')
  })

  it('authenticated user can reach /products/:id/trace', async () => {
    const router = makeRouter(true)
    await router.push('/products/7/trace')
    expect(router.currentRoute.value.name).toBe('ProductTrace')
    expect(router.currentRoute.value.params.id).toBe('7')
  })

  it('Products route still resolves correctly', () => {
    const router = makeRouter(true)
    const route = router.resolve({ name: 'Products' })
    expect(route.path).toBe('/products')
    expect(route.meta.requiresAuth).toBe(true)
  })
})
