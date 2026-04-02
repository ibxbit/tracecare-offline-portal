// Global test setup for jsdom environment
import { vi } from 'vitest'

// Stub localStorage
const _store = {}
globalThis.localStorage = {
  getItem: (k) => _store[k] ?? null,
  setItem: (k, v) => { _store[k] = String(v) },
  removeItem: (k) => { delete _store[k] },
  clear: () => { Object.keys(_store).forEach(k => delete _store[k]) },
  get length() { return Object.keys(_store).length },
  key: (i) => Object.keys(_store)[i] ?? null,
}

// navigator.onLine
Object.defineProperty(navigator, 'onLine', { value: true, writable: true })

// Suppress console.warn noise from vue-router
globalThis.console.warn = vi.fn()
