<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Exam Packages</h1>
        <p class="text-slate-500 text-sm mt-1">Browse available exam bundles with USD pricing</p>
      </div>
      <div class="flex gap-2">
        <RouterLink v-if="authStore.isRole('admin')" to="/packages/setup"
          class="btn-primary">Manage Packages</RouterLink>
        <RouterLink to="/quick-views" class="btn-secondary text-sm">My Quick Views</RouterLink>
      </div>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-6">
      <input v-model="search" @input="debouncedFetch" type="text"
        class="input max-w-xs" placeholder="Search packages..." />
      <label class="flex items-center gap-2 text-sm text-slate-600">
        <input v-model="activeOnly" @change="fetchPackages" type="checkbox" class="rounded" />
        Active only
      </label>
      <span v-if="fromCache" class="text-xs text-amber-600 self-center">📦 Offline cache</span>
    </div>

    <div v-if="loading" class="text-center py-16 text-slate-400">Loading packages...</div>
    <div v-else-if="!packages.length" class="text-center py-16 text-slate-400">No packages found.</div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
      <div v-for="pkg in packages" :key="pkg.id"
        class="bg-white rounded-xl border border-slate-200 shadow-sm hover:shadow-md transition-shadow p-6">
        <!-- Header row -->
        <div class="flex items-start justify-between mb-3">
          <div>
            <h2 class="text-lg font-semibold text-slate-900">{{ pkg.name }}</h2>
            <span class="text-xs text-slate-400">v{{ pkg.version }}</span>
          </div>
          <div class="flex flex-col items-end gap-1">
            <span :class="['text-xs font-medium px-2 py-0.5 rounded-full',
              pkg.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
              {{ pkg.is_active ? 'Active' : 'Inactive' }}
            </span>
          </div>
        </div>

        <!-- Price & validity -->
        <div class="flex items-center gap-4 mb-4">
          <div class="text-2xl font-bold text-blue-700">
            ${{ Number(pkg.price).toFixed(2) }}
          </div>
          <div v-if="pkg.validity_window_days" class="text-sm text-slate-500">
            Valid {{ pkg.validity_window_days }} days
          </div>
        </div>

        <!-- Items preview -->
        <div v-if="pkg.items?.length" class="mb-4">
          <p class="text-xs font-semibold text-slate-500 uppercase mb-2">Included Tests</p>
          <div class="flex flex-wrap gap-1.5">
            <span v-for="item in pkg.items.slice(0, 6)" :key="item.id"
              class="text-xs bg-blue-50 text-blue-700 rounded-full px-2 py-0.5">
              {{ item.exam_item_code || item.code }}
            </span>
            <span v-if="pkg.items.length > 6"
              class="text-xs bg-slate-100 text-slate-500 rounded-full px-2 py-0.5">
              +{{ pkg.items.length - 6 }} more
            </span>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-between pt-3 border-t border-slate-100">
          <RouterLink v-if="authStore.isRole('admin', 'clinic_staff')" :to="`/packages/${pkg.id}/diff`"
            class="text-sm text-blue-600 hover:text-blue-800 font-medium">
            What changed?
          </RouterLink>
          <span v-else />
          <button @click="toggleQuickView(pkg)"
            :class="['text-xs px-3 py-1.5 rounded-lg border transition-colors',
              qvStore.isSaved(pkg.id, 'package')
                ? 'bg-amber-50 border-amber-300 text-amber-700'
                : 'border-slate-200 text-slate-500 hover:border-blue-300 hover:text-blue-600']">
            {{ qvStore.isSaved(pkg.id, 'package') ? '★ Saved' : '☆ Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api/index.js'
import { useAuthStore } from '../stores/auth.js'
import { useQuickViewStore } from '../stores/quickviews.js'
import { useOfflineStore } from '../stores/offline.js'

const authStore = useAuthStore()
const qvStore = useQuickViewStore()
const offlineStore = useOfflineStore()

const packages = ref([])
const loading = ref(true)
const search = ref('')
const activeOnly = ref(true)
const fromCache = ref(false)
let debounceTimer = null

async function fetchPackages() {
  loading.value = true
  try {
    const { data, fromCache: cached } = await offlineStore.fetchWithCache(
      `packages_${activeOnly.value}_${search.value}`,
      async () => {
        const res = await api.get('/packages', {
          params: { active_only: activeOnly.value, name: search.value || undefined, limit: 100 },
        })
        return res.data
      }
    )
    packages.value = data
    fromCache.value = cached
  } catch {
    packages.value = []
  } finally {
    loading.value = false
  }
}

function debouncedFetch() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchPackages, 300)
}

function toggleQuickView(pkg) {
  if (qvStore.isSaved(pkg.id, 'package')) {
    qvStore.remove(pkg.id, 'package')
  } else {
    const result = qvStore.add({
      id: pkg.id, type: 'package',
      label: `${pkg.name} v${pkg.version}`,
      route: `/packages`,
      meta: { price: pkg.price, validity: pkg.validity_window_days },
    })
    if (!result.added) alert(result.reason)
  }
}

onMounted(fetchPackages)
</script>
