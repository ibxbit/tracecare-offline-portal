<template>
  <nav class="fixed top-0 left-0 right-0 z-50 bg-blue-700 text-white shadow-lg">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div class="flex items-center justify-between h-16">
        <!-- Logo -->
        <div class="flex items-center gap-3">
          <svg class="w-8 h-8 text-blue-200" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
          </svg>
          <RouterLink to="/dashboard" class="font-bold text-lg text-white hover:text-blue-100">
            TraceCare
          </RouterLink>
        </div>

        <!-- Navigation Links -->
        <div class="hidden md:flex items-center gap-1">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="px-3 py-2 rounded-md text-sm font-medium text-blue-100 hover:text-white hover:bg-blue-600 transition-colors"
            active-class="bg-blue-800 text-white"
          >
            {{ item.label }}
          </RouterLink>
        </div>

        <!-- Right side -->
        <div class="flex items-center gap-3">
          <!-- Notification bell -->
          <RouterLink to="/notifications" class="relative text-blue-200 hover:text-white transition-colors p-1">
            <svg class="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <span v-if="notifStore.unreadCount > 0"
              class="absolute -top-1 -right-1 bg-red-500 text-white text-xs rounded-full min-w-[18px] h-[18px] flex items-center justify-center px-1 font-bold">
              {{ notifStore.unreadCount > 99 ? '99+' : notifStore.unreadCount }}
            </span>
          </RouterLink>

          <!-- Quick views -->
          <RouterLink to="/quick-views" class="text-blue-200 hover:text-white text-sm transition-colors" title="Quick Views">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
                d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
            </svg>
          </RouterLink>

          <div class="text-sm text-blue-200">
            <span class="font-medium text-white">{{ authStore.user?.username }}</span>
            <span class="ml-1 text-xs">({{ formatRole(authStore.userRole) }})</span>
          </div>
          <RouterLink to="/profile" class="text-blue-200 hover:text-white text-sm transition-colors">Profile</RouterLink>
          <button @click="handleLogout"
            class="px-3 py-1.5 text-sm rounded-md bg-blue-800 hover:bg-blue-900 text-white transition-colors">
            Logout
          </button>
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import { useNotificationStore } from '../stores/notifications.js'

const authStore = useAuthStore()
const notifStore = useNotificationStore()
const router = useRouter()

const allNavItems = [
  { to: '/dashboard',    label: 'Dashboard',   roles: null },
  { to: '/packages',     label: 'Packages',    roles: null },
  { to: '/packages/setup', label: 'Pkg Setup',  roles: ['admin'] },
  { to: '/exams',        label: 'Exams',       roles: ['admin', 'clinic_staff'] },
  { to: '/catalog',      label: 'Catalog',     roles: null },
  { to: '/reviews',      label: 'Reviews',     roles: null },
  { to: '/messages',     label: 'Messages',    roles: null },
  { to: '/cms',          label: 'CMS',         roles: ['admin', 'clinic_staff', 'catalog_manager'] },
  { to: '/admin',        label: 'Admin',       roles: ['admin'] },
  { to: '/users',        label: 'Users',       roles: ['admin'] },
]

const navItems = computed(() =>
  allNavItems.filter(item => !item.roles || item.roles.includes(authStore.userRole))
)

function formatRole(role) {
  return { admin: 'Admin', clinic_staff: 'Staff', catalog_manager: 'Catalog', end_user: 'User' }[role] || role
}

async function handleLogout() {
  await authStore.logout()
  notifStore.stopPolling()
  router.push('/login')
}
</script>
