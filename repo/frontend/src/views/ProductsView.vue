<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Agricultural Products</h1>
        <p class="text-slate-500 text-sm mt-1">Track and trace agricultural product lifecycle</p>
      </div>
      <RoleGuard :roles="['admin', 'catalog_manager']">
        <button @click="showCreate = true" class="btn-primary">+ Add Product</button>
      </RoleGuard>
    </div>

    <DataTable
      :columns="columns"
      :rows="products"
      :loading="loading"
      empty-text="No products found."
    >
      <template #cell-harvest_date="{ value }">
        {{ value ? new Date(value).toLocaleDateString() : '-' }}
      </template>
      <template #cell-expiry_date="{ value }">
        {{ value ? new Date(value).toLocaleDateString() : '-' }}
      </template>
      <template #actions="{ row }">
        <div class="flex justify-end gap-2">
          <RouterLink :to="`/products/${row.id}/trace`" class="btn btn-sm btn-secondary">
            Trace
          </RouterLink>
          <RoleGuard :roles="['admin', 'catalog_manager']">
            <button @click="confirmDelete(row)" class="btn btn-sm btn-danger">Delete</button>
          </RoleGuard>
        </div>
      </template>
    </DataTable>

    <!-- Create Product Modal -->
    <Modal v-model="showCreate" title="Add Product" size="lg">
      <form @submit.prevent="handleCreate" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Product Name *</label>
            <input v-model="form.name" type="text" class="input" required placeholder="e.g., Organic Tomatoes" />
          </div>
          <div>
            <label class="label">SKU *</label>
            <input v-model="form.sku" type="text" class="input" required placeholder="e.g., ORG-TOM-001" />
          </div>
          <div>
            <label class="label">Origin</label>
            <input v-model="form.origin" type="text" class="input" placeholder="Farm/Region" />
          </div>
          <div>
            <label class="label">Batch Number</label>
            <input v-model="form.batch_number" type="text" class="input" placeholder="Batch ID" />
          </div>
          <div>
            <label class="label">Harvest Date</label>
            <input v-model="form.harvest_date" type="date" class="input" />
          </div>
          <div>
            <label class="label">Processing Date</label>
            <input v-model="form.processing_date" type="date" class="input" />
          </div>
          <div>
            <label class="label">Expiry Date</label>
            <input v-model="form.expiry_date" type="date" class="input" />
          </div>
        </div>
        <div v-if="createError" class="text-sm text-red-600">{{ createError }}</div>
      </form>
      <template #footer>
        <button @click="showCreate = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreate" :disabled="creating" class="btn-primary">
          {{ creating ? 'Adding...' : 'Add Product' }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm Modal -->
    <Modal v-model="showDelete" title="Confirm Delete" size="sm">
      <p class="text-slate-600">Delete product <strong>{{ selectedProduct?.name }}</strong>? This cannot be undone.</p>
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
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api/index.js'
import DataTable from '../components/DataTable.vue'
import Modal from '../components/Modal.vue'
import RoleGuard from '../components/RoleGuard.vue'

const products = ref([])
const loading = ref(true)
const showCreate = ref(false)
const showDelete = ref(false)
const creating = ref(false)
const deleting = ref(false)
const createError = ref('')
const selectedProduct = ref(null)

const form = ref({
  name: '', sku: '', origin: '', batch_number: '',
  harvest_date: '', processing_date: '', expiry_date: '',
})

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'name', label: 'Name' },
  { key: 'sku', label: 'SKU' },
  { key: 'origin', label: 'Origin' },
  { key: 'batch_number', label: 'Batch' },
  { key: 'harvest_date', label: 'Harvested' },
  { key: 'expiry_date', label: 'Expires' },
]

async function fetchProducts() {
  loading.value = true
  try {
    const res = await api.get('/products')
    products.value = res.data
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  createError.value = ''
  creating.value = true
  try {
    const payload = Object.fromEntries(
      Object.entries(form.value).filter(([, v]) => v !== '')
    )
    await api.post('/products', payload)
    showCreate.value = false
    form.value = { name: '', sku: '', origin: '', batch_number: '', harvest_date: '', processing_date: '', expiry_date: '' }
    await fetchProducts()
  } catch (err) {
    createError.value = err.response?.data?.detail || 'Failed to add product.'
  } finally {
    creating.value = false
  }
}

function confirmDelete(product) {
  selectedProduct.value = product
  showDelete.value = true
}

async function handleDelete() {
  deleting.value = true
  try {
    await api.delete(`/products/${selectedProduct.value.id}`)
    showDelete.value = false
    await fetchProducts()
  } finally {
    deleting.value = false
  }
}

onMounted(fetchProducts)
</script>
