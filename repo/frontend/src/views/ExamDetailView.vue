<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-6">
      <RouterLink to="/exams" class="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1">
        &larr; Back to Exams
      </RouterLink>
    </div>

    <div v-if="loading" class="text-center py-16 text-slate-400">Loading exam...</div>

    <div v-else-if="exam" class="space-y-6">
      <!-- Header -->
      <div class="card">
        <div class="flex items-start justify-between">
          <div>
            <h1 class="text-2xl font-bold text-slate-900">{{ exam.exam_type }}</h1>
            <p class="text-slate-500 text-sm mt-1">Exam #{{ exam.id }}</p>
          </div>
          <StatusBadge :status="exam.status" />
        </div>

        <div class="mt-6 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p class="text-slate-500">Patient ID</p>
            <p class="font-medium text-slate-800">#{{ exam.patient_id }}</p>
          </div>
          <div>
            <p class="text-slate-500">Staff ID</p>
            <p class="font-medium text-slate-800">#{{ exam.staff_id }}</p>
          </div>
          <div>
            <p class="text-slate-500">Scheduled</p>
            <p class="font-medium text-slate-800">{{ formatDate(exam.scheduled_at) }}</p>
          </div>
          <div>
            <p class="text-slate-500">Completed</p>
            <p class="font-medium text-slate-800">{{ exam.completed_at ? formatDate(exam.completed_at) : '-' }}</p>
          </div>
        </div>
      </div>

      <!-- Findings & Status Update -->
      <div class="card">
        <h3 class="text-lg font-semibold text-slate-800 mb-4">Exam Findings & Status</h3>

        <div v-if="editing" class="space-y-4">
          <div>
            <label class="label">Status</label>
            <select v-model="editForm.status" class="input">
              <option value="scheduled">Scheduled</option>
              <option value="in_progress">In Progress</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>
          </div>
          <div>
            <label class="label">Findings (encrypted at rest)</label>
            <textarea v-model="editForm.findings" class="input" rows="6" placeholder="Enter clinical findings..." />
          </div>
          <div>
            <label class="label">Notes</label>
            <textarea v-model="editForm.notes" class="input" rows="3" placeholder="Additional notes..." />
          </div>
          <div v-if="editForm.status === 'completed'">
            <label class="label">Completed At</label>
            <input v-model="editForm.completed_at" type="datetime-local" class="input" />
          </div>
          <div v-if="saveError" class="text-sm text-red-600">{{ saveError }}</div>
          <div class="flex gap-3">
            <button @click="saveEdit" :disabled="saving" class="btn-primary">
              {{ saving ? 'Saving...' : 'Save Changes' }}
            </button>
            <button @click="editing = false" class="btn-secondary">Cancel</button>
          </div>
        </div>

        <div v-else>
          <div class="mb-4">
            <p class="text-sm text-slate-500 mb-1">Findings</p>
            <div class="bg-slate-50 rounded-lg p-4 text-sm text-slate-800 min-h-16 whitespace-pre-wrap">
              {{ exam.findings || 'No findings recorded yet.' }}
            </div>
          </div>
          <div v-if="exam.notes" class="mb-4">
            <p class="text-sm text-slate-500 mb-1">Notes</p>
            <div class="bg-slate-50 rounded-lg p-4 text-sm text-slate-800 whitespace-pre-wrap">
              {{ exam.notes }}
            </div>
          </div>
          <RoleGuard :roles="['admin', 'clinic_staff']">
            <button @click="startEdit" class="btn-primary">Edit Findings & Status</button>
          </RoleGuard>
        </div>
      </div>
    </div>

    <div v-else class="text-center py-16 text-slate-400">Exam not found.</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, RouterLink } from 'vue-router'
import api from '../api/index.js'
import StatusBadge from '../components/StatusBadge.vue'
import RoleGuard from '../components/RoleGuard.vue'

const route = useRoute()
const exam = ref(null)
const loading = ref(true)
const editing = ref(false)
const saving = ref(false)
const saveError = ref('')

const editForm = ref({
  status: '',
  findings: '',
  notes: '',
  completed_at: '',
})

function formatDate(d) {
  return new Date(d).toLocaleString()
}

async function fetchExam() {
  loading.value = true
  try {
    const res = await api.get(`/exams/${route.params.id}`)
    exam.value = res.data
  } finally {
    loading.value = false
  }
}

function startEdit() {
  editForm.value = {
    status: exam.value.status,
    findings: exam.value.findings || '',
    notes: exam.value.notes || '',
    completed_at: exam.value.completed_at
      ? new Date(exam.value.completed_at).toISOString().slice(0, 16)
      : '',
  }
  editing.value = true
}

async function saveEdit() {
  saveError.value = ''
  saving.value = true
  try {
    const payload = {
      status: editForm.value.status,
      findings: editForm.value.findings || null,
      notes: editForm.value.notes || null,
      completed_at: editForm.value.completed_at
        ? new Date(editForm.value.completed_at).toISOString()
        : null,
    }
    const res = await api.put(`/exams/${exam.value.id}`, payload)
    exam.value = res.data
    editing.value = false
  } catch (err) {
    saveError.value = err.response?.data?.detail || 'Failed to save changes.'
  } finally {
    saving.value = false
  }
}

onMounted(fetchExam)
</script>
