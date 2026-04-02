<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center gap-3 mb-6">
      <button @click="$router.back()" class="text-slate-400 hover:text-slate-700">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Package Diff</h1>
        <p class="text-slate-500 text-sm mt-1">Compare versions to see what changed</p>
      </div>
    </div>

    <!-- Version selector -->
    <div class="bg-white rounded-xl border border-slate-200 p-5 mb-6">
      <div class="grid grid-cols-2 gap-6">
        <div>
          <label class="label">Base Version</label>
          <select v-model.number="baseId" @change="loadDiff" class="input">
            <option v-for="v in versions" :key="v.id" :value="v.id">
              {{ v.name }} v{{ v.version }} — ${{ Number(v.price).toFixed(2) }}
              {{ v.is_active ? '(Active)' : '' }}
            </option>
          </select>
        </div>
        <div>
          <label class="label">Compare With</label>
          <select v-model.number="otherId" @change="loadDiff" class="input">
            <option v-for="v in versions" :key="v.id" :value="v.id">
              {{ v.name }} v{{ v.version }} — ${{ Number(v.price).toFixed(2) }}
              {{ v.is_active ? '(Active)' : '' }}
            </option>
          </select>
        </div>
      </div>
    </div>

    <div v-if="diffLoading" class="text-center py-16 text-slate-400">Computing diff…</div>
    <div v-else-if="!diff" class="text-center py-16 text-slate-400">Select two versions to compare.</div>
    <div v-else>
      <!-- Metadata changes -->
      <section v-if="diff.metadata_changes.length" class="mb-6">
        <h2 class="text-base font-semibold text-slate-700 mb-3">Metadata Changes</h2>
        <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <table class="w-full text-sm">
            <thead class="bg-slate-50 border-b border-slate-200">
              <tr>
                <th class="text-left px-4 py-2.5 font-semibold text-slate-600">Field</th>
                <th class="text-left px-4 py-2.5 font-semibold text-red-500">Before</th>
                <th class="text-left px-4 py-2.5 font-semibold text-green-600">After</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100">
              <tr v-for="change in diff.metadata_changes" :key="change.field" class="hover:bg-slate-50">
                <td class="px-4 py-2.5 font-medium text-slate-700 capitalize">{{ change.field.replace(/_/g, ' ') }}</td>
                <td class="px-4 py-2.5 text-red-600 line-through">{{ formatValue(change.field, change.before) }}</td>
                <td class="px-4 py-2.5 text-green-700 font-medium">{{ formatValue(change.field, change.after) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <!-- Added items -->
      <section v-if="diff.items_added.length" class="mb-6">
        <h2 class="text-base font-semibold text-slate-700 mb-3">
          Tests Added <span class="ml-1 bg-green-100 text-green-700 text-xs px-1.5 rounded-full">+{{ diff.items_added.length }}</span>
        </h2>
        <div class="flex flex-wrap gap-2">
          <span v-for="item in diff.items_added" :key="item.exam_item_id"
            class="bg-green-50 border border-green-200 text-green-800 text-sm px-3 py-1.5 rounded-lg">
            + {{ item.code }} — {{ item.name }}
          </span>
        </div>
      </section>

      <!-- Removed items -->
      <section v-if="diff.items_removed.length" class="mb-6">
        <h2 class="text-base font-semibold text-slate-700 mb-3">
          Tests Removed <span class="ml-1 bg-red-100 text-red-600 text-xs px-1.5 rounded-full">-{{ diff.items_removed.length }}</span>
        </h2>
        <div class="flex flex-wrap gap-2">
          <span v-for="item in diff.items_removed" :key="item.exam_item_id"
            class="bg-red-50 border border-red-200 text-red-800 text-sm px-3 py-1.5 rounded-lg line-through">
            {{ item.code }} — {{ item.name }}
          </span>
        </div>
      </section>

      <!-- Changed items -->
      <section v-if="diff.items_changed.length" class="mb-6">
        <h2 class="text-base font-semibold text-slate-700 mb-3">Tests Changed</h2>
        <div class="space-y-3">
          <div v-for="c in diff.items_changed" :key="c.exam_item_id"
            class="bg-white rounded-xl border border-amber-200 p-4">
            <p class="font-semibold text-slate-800 mb-2">{{ c.code }} — {{ c.name }}</p>
            <div class="space-y-1 text-sm">
              <div v-for="field in c.changed_fields" :key="field.field" class="flex gap-4">
                <span class="text-slate-500 w-28 shrink-0 capitalize">{{ field.field.replace(/_/g, ' ') }}</span>
                <span class="text-red-500 line-through">{{ field.before }}</span>
                <span class="text-slate-400">→</span>
                <span class="text-green-700 font-medium">{{ field.after }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- No changes -->
      <div v-if="!diff.metadata_changes.length && !diff.items_added.length && !diff.items_removed.length && !diff.items_changed.length"
        class="text-center py-12 text-slate-400 bg-white rounded-xl border border-slate-200">
        No differences between these two versions.
      </div>

      <!-- Confirm edition (clinic staff) -->
      <div v-if="authStore.isRole('admin', 'clinic_staff')" class="mt-8 flex justify-end">
        <button @click="confirmEdition" class="btn-primary">
          ✓ Confirm — Activate v{{ selectedOtherVersion?.version }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api/index.js'
import { useAuthStore } from '../stores/auth.js'

const route = useRoute()
const authStore = useAuthStore()

const versions = ref([])
const baseId = ref(null)
const otherId = ref(null)
const diff = ref(null)
const diffLoading = ref(false)

const selectedOtherVersion = computed(() => versions.value.find(v => v.id === otherId.value))

function formatValue(field, val) {
  if (val === null || val === undefined) return '—'
  if (field === 'price') return `$${Number(val).toFixed(2)}`
  if (field === 'validity_window_days') return val ? `${val} days` : 'None'
  return String(val)
}

async function loadDiff() {
  if (!baseId.value || !otherId.value || baseId.value === otherId.value) return
  diffLoading.value = true
  try {
    const res = await api.get(`/packages/${baseId.value}/diff/${otherId.value}`)
    diff.value = res.data
  } catch (err) {
    diff.value = null
    alert(err.response?.data?.detail || 'Failed to load diff')
  } finally {
    diffLoading.value = false
  }
}

async function confirmEdition() {
  if (!selectedOtherVersion.value) return
  if (!confirm(`Activate "${selectedOtherVersion.value.name} v${selectedOtherVersion.value.version}"? This will deactivate other versions.`)) return
  await api.patch(`/packages/${otherId.value}/activate`)
  alert('Package activated successfully.')
}

onMounted(async () => {
  const pkgId = route.params.id
  // Load all versions of this package
  const res = await api.get(`/packages/${pkgId}/versions`)
  versions.value = res.data
  if (versions.value.length >= 2) {
    baseId.value = versions.value[versions.value.length - 2].id
    otherId.value = versions.value[versions.value.length - 1].id
    await loadDiff()
  } else if (versions.value.length === 1) {
    baseId.value = versions.value[0].id
    otherId.value = versions.value[0].id
  }
})
</script>
