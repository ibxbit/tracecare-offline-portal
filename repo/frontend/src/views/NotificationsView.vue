<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Notifications</h1>
        <p class="text-slate-500 text-sm mt-1">
          <span v-if="notifStore.unreadCount > 0" class="text-blue-600 font-medium">{{ notifStore.unreadCount }} unread</span>
          <span v-else>All caught up</span>
        </p>
      </div>
      <div class="flex gap-2">
        <button @click="notifStore.markAllRead()" v-if="notifStore.unreadCount > 0"
          class="btn-secondary text-sm">Mark all read</button>
      </div>
    </div>

    <!-- Type filter -->
    <div class="flex flex-wrap gap-2 mb-5">
      <button v-for="f in typeFilters" :key="f.value" @click="activeType = f.value; loadNotifications()"
        :class="['text-xs px-3 py-1.5 rounded-full border transition-colors font-medium',
          activeType === f.value ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-200 text-slate-600 hover:border-blue-300']">
        {{ f.label }}
      </button>
    </div>

    <div v-if="loading" class="text-center py-16 text-slate-400">Loading…</div>
    <div v-else-if="!notifStore.notifications.length" class="text-center py-16 text-slate-400 bg-white rounded-xl border border-slate-200">
      No notifications.
    </div>
    <div v-else class="space-y-2">
      <div v-for="n in notifStore.notifications" :key="n.id"
        :class="['bg-white rounded-xl border p-4 flex gap-3 transition-colors',
          n.is_read ? 'border-slate-200' : 'border-blue-200 bg-blue-50']">

        <!-- Icon -->
        <div :class="['shrink-0 w-9 h-9 rounded-full flex items-center justify-center text-base', iconBg(n.notification_type)]">
          {{ iconEmoji(n.notification_type) }}
        </div>

        <div class="flex-1 min-w-0">
          <div class="flex items-start justify-between gap-2">
            <p :class="['text-sm font-medium', n.is_read ? 'text-slate-700' : 'text-slate-900']">{{ n.title }}</p>
            <span class="text-xs text-slate-400 shrink-0">{{ formatDate(n.created_at) }}</span>
          </div>
          <p class="text-xs text-slate-500 mt-0.5">{{ n.body }}</p>
          <div class="flex items-center gap-3 mt-2">
            <span :class="['text-xs px-1.5 py-0.5 rounded-full font-medium', statusColor(n.status)]">
              {{ n.status }}
            </span>
            <span v-if="n.event_subtype" class="text-xs text-slate-400">{{ n.event_subtype }}</span>
          </div>
        </div>

        <div class="shrink-0 flex flex-col gap-1">
          <button v-if="!n.is_read" @click="notifStore.markRead(n.id)"
            class="text-xs text-blue-600 hover:text-blue-800">Read</button>
          <button @click="notifStore.deleteNotification(n.id)"
            class="text-xs text-slate-400 hover:text-red-500">Delete</button>
        </div>
      </div>
    </div>

    <!-- Preferences link -->
    <div class="mt-6 p-4 bg-slate-50 rounded-xl border border-slate-200 text-center">
      <p class="text-sm text-slate-600 mb-2">Manage what notifications you receive</p>
      <RouterLink to="/messages" class="text-sm text-blue-600 hover:underline font-medium">
        Go to Notification Preferences →
      </RouterLink>
    </div>

    <!-- Admin metrics (admin only) -->
    <div v-if="authStore.isRole('admin') && metrics" class="mt-8 bg-white rounded-xl border border-slate-200 p-5">
      <h2 class="text-base font-semibold text-slate-900 mb-4">Delivery Metrics (Admin)</h2>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div class="text-center">
          <div class="text-2xl font-bold text-slate-900">{{ metrics.total_delivered ?? 0 }}</div>
          <div class="text-xs text-slate-500">Delivered</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-amber-600">{{ metrics.total_retrying ?? 0 }}</div>
          <div class="text-xs text-slate-500">Retrying</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-red-600">{{ metrics.total_failed ?? 0 }}</div>
          <div class="text-xs text-slate-500">Failed</div>
        </div>
        <div class="text-center">
          <div class="text-2xl font-bold text-blue-600">{{ metrics.total_pending ?? 0 }}</div>
          <div class="text-xs text-slate-500">Pending</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api/index.js'
import { useNotificationStore } from '../stores/notifications.js'
import { useAuthStore } from '../stores/auth.js'

const notifStore = useNotificationStore()
const authStore = useAuthStore()

const loading = ref(false)
const activeType = ref('')
const metrics = ref(null)

const typeFilters = [
  { value: '', label: 'All' },
  { value: 'order_status', label: 'Orders' },
  { value: 'message', label: 'Messages' },
  { value: 'system', label: 'System' },
  { value: 'info', label: 'Info' },
]

function formatDate(d) { return d ? new Date(d).toLocaleString() : '' }

function iconEmoji(type) {
  return { order_status: '📦', message: '💬', system: '⚙️', info: 'ℹ️' }[type] ?? '🔔'
}

function iconBg(type) {
  return { order_status: 'bg-blue-100', message: 'bg-purple-100', system: 'bg-slate-100', info: 'bg-green-100' }[type] ?? 'bg-slate-100'
}

function statusColor(s) {
  return { delivered: 'bg-green-100 text-green-700', pending: 'bg-yellow-100 text-yellow-700',
    retrying: 'bg-orange-100 text-orange-700', failed: 'bg-red-100 text-red-600' }[s] ?? 'bg-slate-100 text-slate-500'
}

async function loadNotifications() {
  loading.value = true
  await notifStore.fetchNotifications(activeType.value ? { notification_type: activeType.value } : {})
  loading.value = false
}

async function loadMetrics() {
  if (!authStore.isRole('admin')) return
  try { const res = await api.get('/notifications/admin/metrics'); metrics.value = res.data } catch {}
}

onMounted(async () => {
  await Promise.all([loadNotifications(), loadMetrics()])
})
</script>
