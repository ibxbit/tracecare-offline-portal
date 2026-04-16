/**
 * Real Vue component mount test for src/views/LoginView.vue.
 *
 * Uses @vue/test-utils to render the actual SFC (not a stub) and exercises:
 *   - form fields bind to v-model
 *   - submit calls authStore.login with the typed credentials
 *   - successful login navigates to /dashboard (or ?redirect= target)
 *   - failed login renders the backend error message in the UI
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'

vi.mock('../api/index.js', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '../api/index.js'
import LoginView from '../views/LoginView.vue'

const stub = { template: '<div>stub</div>' }


async function mountLogin(initialRoute = '/login') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'Login', component: LoginView },
      { path: '/dashboard', name: 'Dashboard', component: stub },
      { path: '/cms', name: 'CMS', component: stub },
    ],
  })
  await router.push(initialRoute)
  await router.isReady()

  const wrapper = mount(LoginView, {
    global: { plugins: [pinia, router] },
  })
  return { wrapper, router }
}


beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})


describe('LoginView.vue — rendered component', () => {
  it('renders username + password fields + submit button', async () => {
    const { wrapper } = await mountLogin()
    expect(wrapper.find('input#username').exists()).toBe(true)
    expect(wrapper.find('input#password').exists()).toBe(true)
    expect(wrapper.find('button[type="submit"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('TraceCare')
  })

  it('typing into inputs updates v-model', async () => {
    const { wrapper } = await mountLogin()
    await wrapper.find('input#username').setValue('alice')
    await wrapper.find('input#password').setValue('Secret@1234')
    expect(wrapper.find('input#username').element.value).toBe('alice')
    expect(wrapper.find('input#password').element.value).toBe('Secret@1234')
  })

  it('submit calls authStore.login and navigates to /dashboard', async () => {
    api.post.mockResolvedValueOnce({ data: { access_token: 'AT', refresh_token: 'RT' } })
    api.get.mockResolvedValueOnce({ data: { id: 1, role: 'admin' } })

    const { wrapper, router } = await mountLogin()
    await wrapper.find('input#username').setValue('admin')
    await wrapper.find('input#password').setValue('Admin@123!')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(api.post).toHaveBeenCalledWith('/auth/login', {
      username: 'admin', password: 'Admin@123!',
    })
    expect(router.currentRoute.value.name).toBe('Dashboard')
  })

  it('honours ?redirect= query param after login', async () => {
    api.post.mockResolvedValueOnce({ data: { access_token: 'AT', refresh_token: 'RT' } })
    api.get.mockResolvedValueOnce({ data: { id: 1, role: 'admin' } })

    const { wrapper, router } = await mountLogin('/login?redirect=/cms')
    await wrapper.find('input#username').setValue('admin')
    await wrapper.find('input#password').setValue('x')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(router.currentRoute.value.path).toBe('/cms')
  })

  it('renders the backend error message when login fails', async () => {
    api.post.mockRejectedValueOnce({
      response: { data: { detail: 'Invalid username or password' } },
    })

    const { wrapper } = await mountLogin()
    await wrapper.find('input#username').setValue('bad')
    await wrapper.find('input#password').setValue('bad')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.text()).toContain('Invalid username or password')
  })

  it('shows a generic message when the error payload is missing detail', async () => {
    api.post.mockRejectedValueOnce(new Error('network'))
    const { wrapper } = await mountLogin()
    await wrapper.find('input#username').setValue('u')
    await wrapper.find('input#password').setValue('p')
    await wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.text().toLowerCase()).toContain('login failed')
  })

  it('disables the submit button while a login request is in flight', async () => {
    let resolveLogin
    api.post.mockImplementationOnce(() => new Promise(res => { resolveLogin = res }))
    const { wrapper } = await mountLogin()
    await wrapper.find('input#username').setValue('u')
    await wrapper.find('input#password').setValue('p')
    wrapper.find('form').trigger('submit.prevent')
    await flushPromises()
    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
    resolveLogin({ data: { access_token: 'AT', refresh_token: 'RT' } })
  })
})
