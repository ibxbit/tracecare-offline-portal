<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Package Setup</h1>
        <p class="text-slate-500 text-sm mt-1">Manage exam package bundles and versions</p>
      </div>
      <button @click="openCreate" class="btn-primary">+ New Package</button>
    </div>

    <!-- Package list -->
    <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-slate-200">
            <tr>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Name</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Version</th>
              <th class="text-right px-4 py-3 font-semibold text-slate-600">Price (USD)</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Validity</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Items</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Status</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="loading"><td colspan="7" class="text-center py-12 text-slate-400">Loading…</td></tr>
            <tr v-else-if="!packages.length"><td colspan="7" class="text-center py-12 text-slate-400">No packages yet.</td></tr>
            <tr v-for="pkg in packages" :key="pkg.id" class="hover:bg-slate-50">
              <td class="px-4 py-3 font-medium text-slate-900">{{ pkg.name }}</td>
              <td class="px-4 py-3 text-slate-500">v{{ pkg.version }}</td>
              <td class="px-4 py-3 text-right font-semibold text-blue-700">${{ Number(pkg.price).toFixed(2) }}</td>
              <td class="px-4 py-3 text-slate-500">{{ pkg.validity_window_days ? pkg.validity_window_days + ' days' : '—' }}</td>
              <td class="px-4 py-3 text-slate-500">{{ pkg.item_count ?? pkg.items?.length ?? 0 }}</td>
              <td class="px-4 py-3">
                <span :class="['text-xs font-medium px-2 py-0.5 rounded-full',
                  pkg.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
                  {{ pkg.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex gap-2">
                  <button @click="viewVersions(pkg)" class="text-xs text-blue-600 hover:underline">Versions</button>
                  <RouterLink :to="`/packages/${pkg.id}/diff`" class="text-xs text-slate-500 hover:text-slate-800">Diff</RouterLink>
                  <button v-if="!pkg.is_active" @click="activatePkg(pkg)"
                    class="text-xs text-green-600 hover:underline">Activate</button>
                  <button v-else @click="deactivatePkg(pkg)"
                    class="text-xs text-red-500 hover:underline">Deactivate</button>
                  <button @click="openNewVersion(pkg)" class="text-xs text-purple-600 hover:underline">+ Version</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ── Create Package Modal ─────────────────────────────────────────────── -->
    <Modal v-model="showCreate" title="Create Package" size="lg">
      <form @submit.prevent="handleCreate" class="space-y-5">
        <!-- Basic fields -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Name *</label>
            <input v-model="createForm.name" type="text" class="input" required placeholder="Annual Health Check" />
          </div>
          <div>
            <label class="label">Price (USD) *</label>
            <input v-model.number="createForm.price" type="number" step="0.01" min="0" class="input" required />
          </div>
        </div>
        <div>
          <label class="label">Validity Window (days)</label>
          <input v-model.number="createForm.validity_window_days" type="number" min="1" class="input"
            placeholder="Leave blank for no expiry" />
        </div>
        <div>
          <label class="label">Description</label>
          <textarea v-model="createForm.description" class="input" rows="2" placeholder="Optional description" />
        </div>

        <!-- Exam item picker -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="label mb-0">Exam Items * (at least one required)</label>
            <span class="text-xs text-slate-400">{{ createForm.items.length }} selected</span>
          </div>
          <div v-if="loadingItems" class="text-sm text-slate-400 py-4 text-center">Loading exam items…</div>
          <div v-else-if="!availableItems.length" class="text-sm text-slate-400 py-4 text-center">
            No active exam items found. Create exam items first.
          </div>
          <div v-else class="border border-slate-200 rounded-lg overflow-hidden">
            <!-- Item search -->
            <div class="px-3 py-2 border-b border-slate-100 bg-slate-50">
              <input v-model="itemSearch" type="text" placeholder="Filter items…"
                class="w-full text-sm bg-transparent outline-none" />
            </div>
            <div class="max-h-52 overflow-y-auto divide-y divide-slate-50">
              <div v-for="item in filteredItems" :key="item.id"
                class="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 transition-colors">
                <input type="checkbox" :id="`ci-${item.id}`"
                  :checked="isItemSelected(createForm.items, item.id)"
                  @change="toggleItem(createForm.items, item.id)"
                  class="rounded border-slate-300" />
                <label :for="`ci-${item.id}`" class="flex-1 text-sm cursor-pointer select-none">
                  <span class="font-mono text-xs text-slate-500 mr-2">{{ item.code }}</span>
                  {{ item.name }}
                </label>
                <!-- Required toggle — only shown when item is selected -->
                <div v-if="isItemSelected(createForm.items, item.id)"
                  class="flex items-center gap-1.5 text-xs shrink-0">
                  <button type="button"
                    :class="['px-2 py-0.5 rounded-full border transition-colors',
                      getItem(createForm.items, item.id)?.is_required
                        ? 'bg-blue-50 border-blue-300 text-blue-700'
                        : 'border-slate-200 text-slate-400']"
                    @click="setRequired(createForm.items, item.id, true)">Required</button>
                  <button type="button"
                    :class="['px-2 py-0.5 rounded-full border transition-colors',
                      !getItem(createForm.items, item.id)?.is_required
                        ? 'bg-amber-50 border-amber-300 text-amber-700'
                        : 'border-slate-200 text-slate-400']"
                    @click="setRequired(createForm.items, item.id, false)">Optional</button>
                </div>
              </div>
            </div>
          </div>
          <!-- Selected summary -->
          <div v-if="createForm.items.length" class="mt-2 flex flex-wrap gap-1.5">
            <span v-for="sel in createForm.items" :key="sel.exam_item_id"
              :class="['text-xs px-2 py-0.5 rounded-full',
                sel.is_required ? 'bg-blue-50 text-blue-700' : 'bg-amber-50 text-amber-700']">
              {{ itemName(sel.exam_item_id) }}
              <span class="opacity-60 ml-0.5">{{ sel.is_required ? '(req)' : '(opt)' }}</span>
            </span>
          </div>
        </div>

        <div v-if="createError" class="text-sm text-red-600 bg-red-50 rounded p-2">{{ createError }}</div>
      </form>
      <template #footer>
        <button @click="showCreate = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreate" :disabled="creating || !createForm.items.length" class="btn-primary">
          {{ creating ? 'Creating…' : 'Create Package' }}
        </button>
      </template>
    </Modal>

    <!-- ── New Version Modal ───────────────────────────────────────────────── -->
    <Modal v-model="showNewVersion" :title="`New Version — ${selectedPkg?.name}`" size="lg">
      <form @submit.prevent="handleNewVersion" class="space-y-5">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">New Price (USD) *</label>
            <input v-model.number="versionForm.price" type="number" step="0.01" min="0" class="input" required />
          </div>
          <div>
            <label class="label">Validity (days)</label>
            <input v-model.number="versionForm.validity_window_days" type="number" min="1" class="input" />
          </div>
        </div>
        <div>
          <label class="label">Change Note</label>
          <textarea v-model="versionForm.change_note" class="input" rows="2" placeholder="What changed in this version?" />
        </div>

        <!-- Exam item picker for new version -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <label class="label mb-0">Exam Items (leave unchanged to keep current)</label>
            <span class="text-xs text-slate-400">{{ versionForm.items.length }} selected</span>
          </div>
          <div v-if="loadingItems" class="text-sm text-slate-400 py-3 text-center">Loading…</div>
          <div v-else class="border border-slate-200 rounded-lg overflow-hidden">
            <div class="px-3 py-2 border-b border-slate-100 bg-slate-50">
              <input v-model="itemSearch" type="text" placeholder="Filter items…"
                class="w-full text-sm bg-transparent outline-none" />
            </div>
            <div class="max-h-48 overflow-y-auto divide-y divide-slate-50">
              <div v-for="item in filteredItems" :key="item.id"
                class="flex items-center gap-3 px-3 py-2 hover:bg-slate-50 transition-colors">
                <input type="checkbox" :id="`vi-${item.id}`"
                  :checked="isItemSelected(versionForm.items, item.id)"
                  @change="toggleItem(versionForm.items, item.id)"
                  class="rounded border-slate-300" />
                <label :for="`vi-${item.id}`" class="flex-1 text-sm cursor-pointer select-none">
                  <span class="font-mono text-xs text-slate-500 mr-2">{{ item.code }}</span>
                  {{ item.name }}
                </label>
                <div v-if="isItemSelected(versionForm.items, item.id)"
                  class="flex items-center gap-1.5 text-xs shrink-0">
                  <button type="button"
                    :class="['px-2 py-0.5 rounded-full border transition-colors',
                      getItem(versionForm.items, item.id)?.is_required
                        ? 'bg-blue-50 border-blue-300 text-blue-700'
                        : 'border-slate-200 text-slate-400']"
                    @click="setRequired(versionForm.items, item.id, true)">Required</button>
                  <button type="button"
                    :class="['px-2 py-0.5 rounded-full border transition-colors',
                      !getItem(versionForm.items, item.id)?.is_required
                        ? 'bg-amber-50 border-amber-300 text-amber-700'
                        : 'border-slate-200 text-slate-400']"
                    @click="setRequired(versionForm.items, item.id, false)">Optional</button>
                </div>
              </div>
            </div>
          </div>
          <p class="text-xs text-slate-400 mt-1">
            If no items are changed, the previous version's composition is carried over.
          </p>
        </div>

        <div v-if="versionError" class="text-sm text-red-600 bg-red-50 rounded p-2">{{ versionError }}</div>
      </form>
      <template #footer>
        <button @click="showNewVersion = false" class="btn-secondary">Cancel</button>
        <button @click="handleNewVersion" :disabled="creatingVersion" class="btn-primary">
          {{ creatingVersion ? 'Creating…' : 'Create Version' }}
        </button>
      </template>
    </Modal>

    <!-- ── Versions History Modal ─────────────────────────────────────────── -->
    <Modal v-model="showVersions" :title="`Versions — ${selectedPkg?.name}`" size="lg">
      <div v-if="versionsLoading" class="py-8 text-center text-slate-400">Loading…</div>
      <div v-else class="space-y-2">
        <div v-for="v in versions" :key="v.id"
          class="flex items-center justify-between p-3 rounded-lg border border-slate-200">
          <div>
            <span class="font-semibold text-slate-900">v{{ v.version }}</span>
            <span class="text-slate-400 ml-2 text-sm">${{ Number(v.price).toFixed(2) }}</span>
            <span v-if="v.validity_window_days" class="text-slate-400 ml-2 text-sm">{{ v.validity_window_days }}d</span>
            <span class="text-slate-400 ml-2 text-sm">{{ v.item_count ?? 0 }} items</span>
          </div>
          <div class="flex items-center gap-3">
            <span :class="['text-xs px-2 py-0.5 rounded-full', v.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
              {{ v.is_active ? 'Active' : 'Inactive' }}
            </span>
            <RouterLink :to="`/packages/${v.id}/diff`" class="text-xs text-blue-600 hover:underline">Diff</RouterLink>
          </div>
        </div>
      </div>
      <template #footer>
        <button @click="showVersions = false" class="btn-secondary">Close</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api/index.js'
import Modal from '../components/Modal.vue'

// ── Package state ─────────────────────────────────────────────────────────────
const packages = ref([])
const loading = ref(true)

// ── Exam items ────────────────────────────────────────────────────────────────
const availableItems = ref([])   // all active exam items from backend
const loadingItems = ref(false)
const itemSearch = ref('')

const filteredItems = computed(() => {
  const q = itemSearch.value.trim().toLowerCase()
  if (!q) return availableItems.value
  return availableItems.value.filter(i =>
    i.name.toLowerCase().includes(q) || i.code.toLowerCase().includes(q)
  )
})

async function fetchExamItems() {
  loadingItems.value = true
  try {
    const res = await api.get('/exam-items', { params: { limit: 500 } })
    availableItems.value = (res.data || []).filter(i => i.is_active !== false)
  } catch {
    availableItems.value = []
  } finally {
    loadingItems.value = false
  }
}

// ── Item-list helpers ─────────────────────────────────────────────────────────
function isItemSelected(list, examItemId) {
  return list.some(i => i.exam_item_id === examItemId)
}

function getItem(list, examItemId) {
  return list.find(i => i.exam_item_id === examItemId)
}

function toggleItem(list, examItemId) {
  const idx = list.findIndex(i => i.exam_item_id === examItemId)
  if (idx >= 0) {
    list.splice(idx, 1)
  } else {
    list.push({ exam_item_id: examItemId, is_required: true })
  }
}

function setRequired(list, examItemId, isRequired) {
  const entry = list.find(i => i.exam_item_id === examItemId)
  if (entry) entry.is_required = isRequired
}

function itemName(examItemId) {
  const found = availableItems.value.find(i => i.id === examItemId)
  return found ? found.name : `#${examItemId}`
}

// ── Create package ────────────────────────────────────────────────────────────
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref({ name: '', price: 0, validity_window_days: null, description: '', items: [] })

function openCreate() {
  createForm.value = { name: '', price: 0, validity_window_days: null, description: '', items: [] }
  createError.value = ''
  itemSearch.value = ''
  showCreate.value = true
  fetchExamItems()
}

async function handleCreate() {
  createError.value = ''
  if (!createForm.value.items.length) {
    createError.value = 'Select at least one exam item.'
    return
  }
  creating.value = true
  try {
    await api.post('/packages', {
      name: createForm.value.name,
      description: createForm.value.description || null,
      price: String(createForm.value.price),
      validity_window_days: createForm.value.validity_window_days || null,
      items: createForm.value.items,
    })
    showCreate.value = false
    await fetchPackages()
  } catch (err) {
    createError.value = err.response?.data?.detail || 'Failed to create package.'
  } finally {
    creating.value = false
  }
}

// ── New version ───────────────────────────────────────────────────────────────
const showNewVersion = ref(false)
const creatingVersion = ref(false)
const versionError = ref('')
const selectedPkg = ref(null)
const versionForm = ref({ price: 0, validity_window_days: null, change_note: '', items: [] })

function openNewVersion(pkg) {
  selectedPkg.value = pkg
  // Pre-populate with current version's composition
  const currentItems = (pkg.items || []).map(i => ({
    exam_item_id: i.exam_item_id,
    is_required: i.is_required,
  }))
  versionForm.value = {
    price: pkg.price,
    validity_window_days: pkg.validity_window_days,
    change_note: '',
    items: currentItems,
  }
  versionError.value = ''
  itemSearch.value = ''
  showNewVersion.value = true
  fetchExamItems()
}

async function handleNewVersion() {
  versionError.value = ''
  creatingVersion.value = true
  try {
    const payload = {
      price: String(versionForm.value.price),
      validity_window_days: versionForm.value.validity_window_days || null,
      change_note: versionForm.value.change_note || null,
    }
    // Only include items if they were explicitly modified
    if (versionForm.value.items.length) {
      payload.items = versionForm.value.items
    }
    await api.post(`/packages/${selectedPkg.value.id}/new-version`, payload)
    showNewVersion.value = false
    await fetchPackages()
  } catch (err) {
    versionError.value = err.response?.data?.detail || 'Failed to create version.'
  } finally {
    creatingVersion.value = false
  }
}

// ── Versions history ──────────────────────────────────────────────────────────
const showVersions = ref(false)
const versionsLoading = ref(false)
const versions = ref([])

async function viewVersions(pkg) {
  selectedPkg.value = pkg
  showVersions.value = true
  versionsLoading.value = true
  try {
    const res = await api.get(`/packages/${pkg.id}/versions`)
    versions.value = res.data
  } finally {
    versionsLoading.value = false
  }
}

// ── Activate / deactivate ─────────────────────────────────────────────────────
async function activatePkg(pkg) {
  if (!confirm(`Activate "${pkg.name} v${pkg.version}"? Other versions of this package will be deactivated.`)) return
  await api.patch(`/packages/${pkg.id}/activate`)
  await fetchPackages()
}

async function deactivatePkg(pkg) {
  if (!confirm(`Deactivate "${pkg.name} v${pkg.version}"?`)) return
  await api.patch(`/packages/${pkg.id}/deactivate`)
  await fetchPackages()
}

// ── Bootstrap ─────────────────────────────────────────────────────────────────
async function fetchPackages() {
  loading.value = true
  try {
    const res = await api.get('/packages', { params: { limit: 200 } })
    packages.value = res.data
  } finally {
    loading.value = false
  }
}

onMounted(fetchPackages)
</script>
