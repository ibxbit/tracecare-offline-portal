import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'

const routes = [
  { path: '/', redirect: '/dashboard' },
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/LoginView.vue'),
    meta: { requiresGuest: true },
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('../views/DashboardView.vue'),
    meta: { requiresAuth: true },
  },

  // ── Exams / Clinic ─────────────────────────────────────────────────────────
  {
    path: '/exams',
    name: 'Exams',
    component: () => import('../views/ExamsView.vue'),
    meta: { requiresAuth: true, roles: ['admin', 'clinic_staff'] },
  },
  {
    path: '/exams/:id',
    name: 'ExamDetail',
    component: () => import('../views/ExamDetailView.vue'),
    meta: { requiresAuth: true, roles: ['admin', 'clinic_staff'] },
  },

  // ── Packages ────────────────────────────────────────────────────────────────
  {
    path: '/packages',
    name: 'Packages',
    component: () => import('../views/PackagesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/packages/setup',
    name: 'PackageSetup',
    component: () => import('../views/PackageSetupView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
  },
  {
    path: '/packages/:id/diff',
    name: 'PackageDiff',
    component: () => import('../views/PackageDiffView.vue'),
    meta: { requiresAuth: true, roles: ['admin', 'clinic_staff'] },
  },

  // ── Catalog ─────────────────────────────────────────────────────────────────
  {
    path: '/catalog',
    name: 'Catalog',
    component: () => import('../views/CatalogView.vue'),
    meta: { requiresAuth: true },
  },

  // ── Reviews ─────────────────────────────────────────────────────────────────
  {
    path: '/reviews',
    name: 'Reviews',
    component: () => import('../views/ReviewsView.vue'),
    meta: { requiresAuth: true },
  },

  // ── Messages & Notifications ─────────────────────────────────────────────────
  {
    path: '/messages',
    name: 'Messages',
    component: () => import('../views/MessagesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/notifications',
    name: 'Notifications',
    component: () => import('../views/NotificationsView.vue'),
    meta: { requiresAuth: true },
  },

  // ── CMS ─────────────────────────────────────────────────────────────────────
  {
    path: '/cms',
    name: 'CMS',
    component: () => import('../views/CMSView.vue'),
    meta: { requiresAuth: true, roles: ['admin', 'clinic_staff', 'catalog_manager'] },
  },

  // ── Admin Console ────────────────────────────────────────────────────────────
  {
    path: '/admin',
    name: 'AdminConsole',
    component: () => import('../views/AdminConsoleView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
  },

  // ── Users ────────────────────────────────────────────────────────────────────
  {
    path: '/users',
    name: 'Users',
    component: () => import('../views/UsersView.vue'),
    meta: { requiresAuth: true, roles: ['admin'] },
  },
  {
    path: '/patients',
    name: 'Patients',
    component: () => import('../views/UsersView.vue'),
    props: { filterRole: 'end_user' },
    meta: { requiresAuth: true, roles: ['admin', 'clinic_staff'] },
  },

  // ── Quick Views (end user saved searches) ───────────────────────────────────
  {
    path: '/quick-views',
    name: 'QuickViews',
    component: () => import('../views/QuickViewsView.vue'),
    meta: { requiresAuth: true },
  },

  // ── Profile ──────────────────────────────────────────────────────────────────
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/ProfileView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('../views/ProductsView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/products/:id/trace',
    name: 'ProductTrace',
    component: () => import('../views/ProductTraceView.vue'),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()

  if (!authStore.user && authStore.isAuthenticated) {
    await authStore.init()
  }

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

export default router
