<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-6">
      <RouterLink to="/products" class="text-sm text-blue-600 hover:text-blue-700">
        &larr; Back to Products
      </RouterLink>
    </div>

    <div v-if="loadingProduct" class="text-center py-16 text-slate-400">Loading...</div>

    <div v-else-if="product">
      <!-- Product Info -->
      <div class="card mb-6">
        <h1 class="text-2xl font-bold text-slate-900">{{ product.name }}</h1>
        <p class="text-slate-500 text-sm mt-1">SKU: {{ product.sku }}</p>
        <div class="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p class="text-slate-500">Origin</p>
            <p class="font-medium text-slate-800">{{ product.origin || '-' }}</p>
          </div>
          <div>
            <p class="text-slate-500">Batch</p>
            <p class="font-medium text-slate-800">{{ product.batch_number || '-' }}</p>
          </div>
          <div>
            <p class="text-slate-500">Harvest Date</p>
            <p class="font-medium text-slate-800">{{ formatDate(product.harvest_date) }}</p>
          </div>
          <div>
            <p class="text-slate-500">Expiry Date</p>
            <p class="font-medium text-slate-800">{{ formatDate(product.expiry_date) }}</p>
          </div>
        </div>
      </div>

      <!-- Trace Timeline -->
      <div class="card">
        <div class="flex items-center justify-between mb-6">
          <h3 class="text-lg font-semibold text-slate-800">Trace Timeline</h3>
          <RoleGuard :roles="['admin', 'catalog_manager']">
            <button @click="showAdd = true" class="btn-primary btn-sm">+ Add Event</button>
          </RoleGuard>
        </div>
        <TraceTimeline :events="events" />
      </div>
    </div>

    <!-- Add Trace Event Modal -->
    <Modal v-model="showAdd" title="Add Trace Event" size="md">
      <form @submit.prevent="handleAddEvent" class="space-y-4">
        <div>
          <label class="label">Event Type *</label>
          <select v-model="eventForm.event_type" class="input" required>
            <option value="">Select type...</option>
            <option value="harvested">Harvested</option>
            <option value="processed">Processed</option>
            <option value="packaged">Packaged</option>
            <option value="shipped">Shipped</option>
            <option value="received">Received</option>
          </select>
        </div>
        <div>
          <label class="label">Location</label>
          <input v-model="eventForm.location" type="text" class="input" placeholder="e.g., Farm A, Processing Plant B" />
        </div>
        <div>
          <label class="label">Timestamp *</label>
          <input v-model="eventForm.timestamp" type="datetime-local" class="input" required />
        </div>
        <div>
          <label class="label">Notes</label>
          <textarea v-model="eventForm.notes" class="input" rows="3" />
        </div>
        <div v-if="addError" class="text-sm text-red-600">{{ addError }}</div>
      </form>
      <template #footer>
        <button @click="showAdd = false" class="btn-secondary">Cancel</button>
        <button @click="handleAddEvent" :disabled="adding" class="btn-primary">
          {{ adding ? 'Adding...' : 'Add Event' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import api from '../api/index.js'
import TraceTimeline from '../components/TraceTimeline.vue'
import Modal from '../components/Modal.vue'
import RoleGuard from '../components/RoleGuard.vue'

const route = useRoute()
const product = ref(null)
const events = ref([])
const loadingProduct = ref(true)
const showAdd = ref(false)
const adding = ref(false)
const addError = ref('')

const eventForm = ref({
  event_type: '',
  location: '',
  timestamp: '',
  notes: '',
})

function formatDate(d) {
  if (!d) return '-'
  return new Date(d).toLocaleDateString()
}

async function fetchData() {
  loadingProduct.value = true
  try {
    const [productRes, eventsRes] = await Promise.all([
      api.get(`/products/${route.params.id}`),
      api.get(`/products/${route.params.id}/trace-events`),
    ])
    product.value = productRes.data
    events.value = eventsRes.data
  } finally {
    loadingProduct.value = false
  }
}

async function handleAddEvent() {
  addError.value = ''
  adding.value = true
  try {
    await api.post(`/products/${route.params.id}/trace-events`, {
      ...eventForm.value,
      timestamp: new Date(eventForm.value.timestamp).toISOString(),
    })
    showAdd.value = false
    eventForm.value = { event_type: '', location: '', timestamp: '', notes: '' }
    const res = await api.get(`/products/${route.params.id}/trace-events`)
    events.value = res.data
  } catch (err) {
    addError.value = err.response?.data?.detail || 'Failed to add trace event.'
  } finally {
    adding.value = false
  }
}

onMounted(fetchData)
</script>
