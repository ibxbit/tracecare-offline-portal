<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-slate-900">Dashboard</h1>
      <p class="text-slate-500 mt-1">
        Welcome back, <span class="font-medium text-slate-700">{{ authStore.user?.username }}</span>
      </p>
    </div>

    <!-- Stats Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
      <div
        v-for="stat in visibleStats"
        :key="stat.label"
        class="card flex items-center gap-4"
      >
        <div :class="['flex-shrink-0 rounded-lg p-3', stat.bgColor]">
          <component :is="stat.icon" :class="['w-6 h-6', stat.iconColor]" />
        </div>
        <div>
          <p class="text-2xl font-bold text-slate-900">
            <span v-if="statsLoading" class="text-slate-300">--</span>
            <span v-else>{{ stat.value }}</span>
          </p>
          <p class="text-sm text-slate-500">{{ stat.label }}</p>
        </div>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <!-- Recent Exams (for staff/admin) -->
      <div v-if="authStore.isRole('admin', 'clinic_staff')" class="card">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">Recent Exams</h3>
        <div v-if="recentExams.length" class="space-y-3">
          <div
            v-for="exam in recentExams.slice(0, 5)"
            :key="exam.id"
            class="flex items-center justify-between py-2 border-b border-slate-100 last:border-0"
          >
            <div>
              <p class="text-sm font-medium text-slate-800">{{ exam.exam_type }}</p>
              <p class="text-xs text-slate-500">Patient #{{ exam.patient_id }}</p>
            </div>
            <StatusBadge :status="exam.status" />
          </div>
        </div>
        <p v-else class="text-sm text-slate-400">No recent exams.</p>
        <RouterLink to="/exams" class="mt-4 block text-sm text-blue-600 hover:text-blue-700 font-medium">
          View all exams &rarr;
        </RouterLink>
      </div>

      <!-- Quick Links -->
      <div class="card">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">Quick Access</h3>
        <div class="space-y-2">
          <RouterLink
            v-for="link in quickLinks"
            :key="link.to"
            :to="link.to"
            class="flex items-center gap-3 p-3 rounded-lg hover:bg-slate-50 transition-colors group"
          >
            <div :class="['p-2 rounded-md', link.bgColor]">
              <component :is="link.icon" :class="['w-5 h-5', link.iconColor]" />
            </div>
            <div>
              <p class="text-sm font-medium text-slate-800 group-hover:text-blue-600">{{ link.label }}</p>
              <p class="text-xs text-slate-500">{{ link.desc }}</p>
            </div>
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, h } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '../stores/auth.js'
import StatusBadge from '../components/StatusBadge.vue'
import api from '../api/index.js'

const authStore = useAuthStore()
const statsLoading = ref(true)
const recentExams = ref([])

const stats = ref([
  { label: 'Total Exams', value: 0, roles: ['admin', 'clinic_staff'], bgColor: 'bg-blue-50', iconColor: 'text-blue-600', icon: makeIcon('M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h8a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01') },
  { label: 'Products', value: 0, roles: null, bgColor: 'bg-green-50', iconColor: 'text-green-600', icon: makeIcon('M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4') },
  { label: 'Catalog Items', value: 0, roles: null, bgColor: 'bg-purple-50', iconColor: 'text-purple-600', icon: makeIcon('M4 6h16M4 10h16M4 14h16M4 18h16') },
  { label: 'Messages', value: 0, roles: null, bgColor: 'bg-amber-50', iconColor: 'text-amber-600', icon: makeIcon('M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z') },
])

function makeIcon(path) {
  return () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '1.5', d: path })
  ])
}

const visibleStats = computed(() =>
  stats.value.filter(s => !s.roles || authStore.isRole(...s.roles))
)

const allQuickLinks = [
  {
    to: '/messages',
    label: 'Messages',
    desc: 'View your inbox',
    bgColor: 'bg-amber-50',
    iconColor: 'text-amber-600',
    roles: null,
    icon: makeIcon('M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'),
  },
  {
    to: '/products',
    label: 'Products',
    desc: 'Agricultural traceability',
    bgColor: 'bg-green-50',
    iconColor: 'text-green-600',
    roles: null,
    icon: makeIcon('M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4'),
  },
  {
    to: '/catalog',
    label: 'Catalog',
    desc: 'Browse catalog items',
    bgColor: 'bg-purple-50',
    iconColor: 'text-purple-600',
    roles: null,
    icon: makeIcon('M4 6h16M4 10h16M4 14h16M4 18h16'),
  },
  {
    to: '/reviews',
    label: 'Reviews',
    desc: 'View and submit reviews',
    bgColor: 'bg-rose-50',
    iconColor: 'text-rose-600',
    roles: null,
    icon: makeIcon('M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z'),
  },
]

const quickLinks = computed(() =>
  allQuickLinks.filter(l => !l.roles || authStore.isRole(...l.roles))
)

onMounted(async () => {
  try {
    const promises = [
      api.get('/products').catch(() => ({ data: [] })),
      api.get('/catalog').catch(() => ({ data: [] })),
      api.get('/messages/inbox').catch(() => ({ data: [] })),
    ]

    if (authStore.isRole('admin', 'clinic_staff')) {
      promises.unshift(api.get('/exams').catch(() => ({ data: [] })))
    }

    const results = await Promise.all(promises)
    let idx = 0

    if (authStore.isRole('admin', 'clinic_staff')) {
      const examsData = results[idx++].data
      stats.value[0].value = examsData.length
      recentExams.value = examsData.slice(0, 5)
    }

    stats.value[1].value = results[idx++].data.length
    stats.value[2].value = results[idx++].data.length
    stats.value[3].value = results[idx].data.length
  } finally {
    statsLoading.value = false
  }
})
</script>
