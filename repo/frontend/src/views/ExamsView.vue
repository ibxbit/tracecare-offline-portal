<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Clinic Exams</h1>
        <p class="text-slate-500 text-sm mt-1">Schedule and manage patient examinations</p>
      </div>
      <RoleGuard :roles="['admin', 'clinic_staff']">
        <button @click="showCreate = true" class="btn-primary">
          + Schedule Exam
        </button>
      </RoleGuard>
    </div>

    <!-- Filters -->
    <div class="flex gap-3 mb-6">
      <select v-model="filterStatus" class="input max-w-xs">
        <option value="">All statuses</option>
        <option value="scheduled">Scheduled</option>
        <option value="in_progress">In Progress</option>
        <option value="completed">Completed</option>
        <option value="cancelled">Cancelled</option>
      </select>
    </div>

    <DataTable
      :columns="columns"
      :rows="filteredExams"
      :loading="loading"
      empty-text="No exams found."
    >
      <template #cell-status="{ value }">
        <StatusBadge :status="value" />
      </template>
      <template #cell-scheduled_at="{ value }">
        {{ new Date(value).toLocaleString() }}
      </template>
      <template #actions="{ row }">
        <div class="flex justify-end gap-2">
          <RouterLink :to="`/exams/${row.id}`" class="btn btn-sm btn-secondary">
            View
          </RouterLink>
          <RoleGuard :roles="['admin']">
            <button @click="confirmDelete(row)" class="btn btn-sm btn-danger">Delete</button>
          </RoleGuard>
        </div>
      </template>
    </DataTable>

    <!-- Create Exam Modal -->
    <Modal v-model="showCreate" title="Schedule New Exam" size="md">
      <form @submit.prevent="handleCreate" class="space-y-4">
        <div>
          <label class="label">Patient</label>
          <select v-model="form.patient_id" class="input" required>
            <option value="">Select patient...</option>
            <option v-for="u in patients" :key="u.id" :value="u.id">
              {{ u.username }} ({{ u.email }})
            </option>
          </select>
        </div>
        <div>
          <label class="label">Exam Type</label>
          <input v-model="form.exam_type" type="text" class="input" placeholder="e.g., Annual Physical" required />
        </div>
        <div>
          <label class="label">Scheduled At</label>
          <input v-model="form.scheduled_at" type="datetime-local" class="input" required />
        </div>
        <div>
          <label class="label">Notes</label>
          <textarea v-model="form.notes" class="input" rows="3" placeholder="Optional notes..." />
        </div>
        <div v-if="createError" class="text-sm text-red-600">{{ createError }}</div>
      </form>
      <template #footer>
        <button @click="showCreate = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreate" :disabled="creating" class="btn-primary">
          {{ creating ? 'Scheduling...' : 'Schedule Exam' }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm Modal -->
    <Modal v-model="showDelete" title="Confirm Delete" size="sm">
      <p class="text-slate-600">Are you sure you want to delete this exam? This action cannot be undone.</p>
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
import { ref, computed, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import api from '../api/index.js'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import Modal from '../components/Modal.vue'
import RoleGuard from '../components/RoleGuard.vue'

const exams = ref([])
const patients = ref([])
const loading = ref(true)
const filterStatus = ref('')
const showCreate = ref(false)
const showDelete = ref(false)
const creating = ref(false)
const deleting = ref(false)
const createError = ref('')
const selectedExam = ref(null)

const form = ref({
  patient_id: '',
  exam_type: '',
  scheduled_at: '',
  notes: '',
})

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'exam_type', label: 'Type' },
  { key: 'patient_id', label: 'Patient ID' },
  { key: 'status', label: 'Status' },
  { key: 'scheduled_at', label: 'Scheduled At', type: 'datetime' },
]

const filteredExams = computed(() => {
  if (!filterStatus.value) return exams.value
  return exams.value.filter(e => e.status === filterStatus.value)
})

async function fetchExams() {
  loading.value = true
  try {
    const res = await api.get('/exams')
    exams.value = res.data
  } finally {
    loading.value = false
  }
}

async function fetchPatients() {
  try {
    const res = await api.get('/users')
    patients.value = res.data.filter(u => u.role === 'end_user')
  } catch {
    // Non-admin may not have access
  }
}

async function handleCreate() {
  createError.value = ''
  creating.value = true
  try {
    await api.post('/exams', {
      ...form.value,
      patient_id: Number(form.value.patient_id),
      scheduled_at: new Date(form.value.scheduled_at).toISOString(),
    })
    showCreate.value = false
    form.value = { patient_id: '', exam_type: '', scheduled_at: '', notes: '' }
    await fetchExams()
  } catch (err) {
    createError.value = err.response?.data?.detail || 'Failed to schedule exam.'
  } finally {
    creating.value = false
  }
}

function confirmDelete(exam) {
  selectedExam.value = exam
  showDelete.value = true
}

async function handleDelete() {
  deleting.value = true
  try {
    await api.delete(`/exams/${selectedExam.value.id}`)
    showDelete.value = false
    await fetchExams()
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  await Promise.all([fetchExams(), fetchPatients()])
})
</script>
