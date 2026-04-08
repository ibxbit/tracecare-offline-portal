<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Catalog</h1>
        <p class="text-slate-500 text-sm mt-1">Manage catalog items and stock levels</p>
      </div>
      <RoleGuard :roles="['admin', 'catalog_manager']">
        <button @click="showCreate = true" class="btn-primary">+ Add Item</button>
      </RoleGuard>
    </div>

    <!-- Search & Filters -->
    <div class="flex flex-wrap gap-3 mb-5">
      <input v-model="filters.search" @input="debouncedFetch" type="text"
        class="input max-w-xs" placeholder="Search name, description, category…" />
      <select v-model="filters.active_only" @change="fetchItems" class="input w-36">
        <option :value="true">Active only</option>
        <option :value="false">All (incl. inactive)</option>
      </select>
      <input v-model.number="filters.price_min" @change="fetchItems" type="number" min="0" step="0.01"
        class="input w-28" placeholder="Min price" />
      <input v-model.number="filters.price_max" @change="fetchItems" type="number" min="0" step="0.01"
        class="input w-28" placeholder="Max price" />
      <input v-model="filters.harvest_date_from" @change="fetchItems" type="date"
        class="input w-40" title="Harvest date from" />
      <input v-model="filters.harvest_date_to" @change="fetchItems" type="date"
        class="input w-40" title="Harvest date to" />
      <label class="flex items-center gap-2 text-sm text-slate-600">
        <input v-model="filters.in_stock" @change="fetchItems" type="checkbox" class="rounded" />
        In-stock only
      </label>
      <input v-model="filters.tags" @input="debouncedFetch" type="text"
        class="input w-44" placeholder="Tags (e.g. organic,premium)" title="Comma-separated tags — matches any" />
      <select v-model.number="filters.priority_min" @change="fetchItems" class="input w-36"
        title="Minimum priority level">
        <option :value="null">Any priority</option>
        <option :value="1">≥ Low (1)</option>
        <option :value="2">≥ Medium (2)</option>
        <option :value="3">≥ High (3)</option>
        <option :value="4">≥ Urgent (4)</option>
        <option :value="5">Critical (5)</option>
      </select>
    </div>

    <DataTable
      :columns="columns"
      :rows="items"
      :loading="loading"
      empty-text="No catalog items found."
    >
      <template #cell-price="{ value }">
        ${{ Number(value).toFixed(2) }}
      </template>
      <template #cell-is_active="{ value }">
        <StatusBadge :status="value ? 'active' : 'inactive'" :label="value ? 'Active' : 'Inactive'" />
      </template>
      <template #cell-stock_quantity="{ row, value }">
        <div class="flex items-center gap-2">
          <span :class="value <= 5 ? 'text-red-600 font-semibold' : 'text-slate-800'">{{ value }}</span>
          <span v-if="value <= 5" class="text-xs text-red-500">(low)</span>
        </div>
      </template>
      <template #actions="{ row }">
        <div class="flex justify-end gap-2">
          <RoleGuard :roles="['admin', 'catalog_manager']">
            <button @click="openStockModal(row)" class="btn btn-sm btn-secondary">Stock</button>
            <button @click="openEdit(row)" class="btn btn-sm btn-secondary">Edit</button>
            <button @click="confirmDelete(row)" class="btn btn-sm btn-danger">Delete</button>
          </RoleGuard>
        </div>
      </template>
    </DataTable>

    <!-- Create/Edit Modal -->
    <Modal v-model="showCreate" :title="editingItem ? 'Edit Item' : 'Add Catalog Item'" size="lg">
      <form @submit.prevent="handleSave" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div class="col-span-2">
            <label class="label">Name *</label>
            <input v-model="form.name" type="text" class="input" required />
          </div>
          <div class="col-span-2">
            <label class="label">Description</label>
            <textarea v-model="form.description" class="input" rows="3" />
          </div>
          <div>
            <label class="label">Category</label>
            <input v-model="form.category" type="text" class="input" />
          </div>
          <div>
            <label class="label">Price *</label>
            <input v-model="form.price" type="number" step="0.01" min="0" class="input" required />
          </div>
          <div>
            <label class="label">Stock Quantity</label>
            <input v-model="form.stock_quantity" type="number" min="0" class="input" />
          </div>
          <div v-if="editingItem" class="flex items-center gap-2 pt-6">
            <input type="checkbox" v-model="form.is_active" id="is_active" class="rounded" />
            <label for="is_active" class="label mb-0">Active</label>
          </div>
        </div>
        <div v-if="saveError" class="text-sm text-red-600">{{ saveError }}</div>
      </form>
      <template #footer>
        <button @click="closeModal" class="btn-secondary">Cancel</button>
        <button @click="handleSave" :disabled="saving" class="btn-primary">
          {{ saving ? 'Saving...' : (editingItem ? 'Update' : 'Add Item') }}
        </button>
      </template>
    </Modal>

    <!-- Stock Adjust Modal -->
    <Modal v-model="showStock" title="Adjust Stock" size="sm">
      <div class="space-y-4">
        <p class="text-sm text-slate-600">
          Current stock for <strong>{{ selectedItem?.name }}</strong>:
          <span class="font-bold text-slate-900">{{ selectedItem?.stock_quantity }}</span>
        </p>
        <div>
          <label class="label">Adjustment (positive = add, negative = remove)</label>
          <input v-model.number="stockAdjust" type="number" class="input" placeholder="e.g., 10 or -5" />
        </div>
        <div v-if="stockError" class="text-sm text-red-600">{{ stockError }}</div>
      </div>
      <template #footer>
        <button @click="showStock = false" class="btn-secondary">Cancel</button>
        <button @click="handleStockAdjust" :disabled="adjusting" class="btn-primary">
          {{ adjusting ? 'Updating...' : 'Apply Adjustment' }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm -->
    <Modal v-model="showDelete" title="Confirm Delete" size="sm">
      <p class="text-slate-600">Delete <strong>{{ selectedItem?.name }}</strong>? This cannot be undone.</p>
      <template #footer>
        <button @click="showDelete = false" class="btn-secondary">Cancel</button>
        <button @click="handleDelete" :disabled="deleting" class="btn-danger">
          {{ deleting ? 'Deleting...' : 'Delete' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api/index.js'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import Modal from '../components/Modal.vue'
import RoleGuard from '../components/RoleGuard.vue'

const items = ref([])
const loading = ref(true)
const showCreate = ref(false)
const showStock = ref(false)
const showDelete = ref(false)
const saving = ref(false)
const adjusting = ref(false)
const deleting = ref(false)
const saveError = ref('')
const stockError = ref('')
const editingItem = ref(null)
const selectedItem = ref(null)
const stockAdjust = ref(0)

const filters = reactive({
  search: '',
  active_only: true,
  price_min: null,
  price_max: null,
  harvest_date_from: '',
  harvest_date_to: '',
  in_stock: false,
  tags: '',
  priority_min: null,
})

let debounceTimer = null
function debouncedFetch() { clearTimeout(debounceTimer); debounceTimer = setTimeout(fetchItems, 300) }

const form = ref({
  name: '', description: '', category: '', price: '0', stock_quantity: 0, is_active: true,
})

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name' },
  { key: 'category', label: 'Category' },
  { key: 'price', label: 'Price' },
  { key: 'stock_quantity', label: 'Stock' },
  { key: 'is_active', label: 'Status' },
]

async function fetchItems() {
  loading.value = true
  try {
    const params = { active_only: filters.active_only, in_stock: filters.in_stock }
    if (filters.search) params.search = filters.search
    if (filters.price_min !== null && filters.price_min !== '') params.price_min = filters.price_min
    if (filters.price_max !== null && filters.price_max !== '') params.price_max = filters.price_max
    if (filters.harvest_date_from) params.harvest_date_from = filters.harvest_date_from
    if (filters.harvest_date_to) params.harvest_date_to = filters.harvest_date_to
    if (filters.tags) params.tags = filters.tags
    if (filters.priority_min !== null) params.priority_min = filters.priority_min
    const res = await api.get('/catalog', { params })
    items.value = res.data
  } finally {
    loading.value = false
  }
}

function openEdit(item) {
  editingItem.value = item
  form.value = {
    name: item.name,
    description: item.description || '',
    category: item.category || '',
    price: item.price,
    stock_quantity: item.stock_quantity,
    is_active: item.is_active,
  }
  showCreate.value = true
}

function closeModal() {
  showCreate.value = false
  editingItem.value = null
  form.value = { name: '', description: '', category: '', price: '0', stock_quantity: 0, is_active: true }
}

async function handleSave() {
  saveError.value = ''
  saving.value = true
  try {
    if (editingItem.value) {
      await api.put(`/catalog/${editingItem.value.id}`, form.value)
    } else {
      await api.post('/catalog', form.value)
    }
    closeModal()
    await fetchItems()
  } catch (err) {
    saveError.value = err.response?.data?.detail || 'Failed to save item.'
  } finally {
    saving.value = false
  }
}

function openStockModal(item) {
  selectedItem.value = item
  stockAdjust.value = 0
  stockError.value = ''
  showStock.value = true
}

async function handleStockAdjust() {
  stockError.value = ''
  adjusting.value = true
  try {
    await api.put(`/catalog/${selectedItem.value.id}/stock`, { adjustment: stockAdjust.value })
    showStock.value = false
    await fetchItems()
  } catch (err) {
    stockError.value = err.response?.data?.detail || 'Failed to adjust stock.'
  } finally {
    adjusting.value = false
  }
}

function confirmDelete(item) {
  selectedItem.value = item
  showDelete.value = true
}

async function handleDelete() {
  deleting.value = true
  try {
    await api.delete(`/catalog/${selectedItem.value.id}`)
    showDelete.value = false
    await fetchItems()
  } finally {
    deleting.value = false
  }
}

onMounted(fetchItems)
</script>
