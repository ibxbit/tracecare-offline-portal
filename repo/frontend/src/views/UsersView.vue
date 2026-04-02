<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">{{ filterRole ? 'Patients' : 'User Management' }}</h1>
        <p class="text-slate-500 text-sm mt-1">{{ filterRole ? 'Manage patient accounts' : 'Manage all user accounts and roles' }}</p>
      </div>
      <button @click="openCreate" class="btn-primary">+ Add User</button>
    </div>

    <DataTable
      :columns="columns"
      :rows="displayUsers"
      :loading="loading"
      empty-text="No users found."
    >
      <template #cell-role="{ value }">
        <StatusBadge :status="value" :label="formatRole(value)" />
      </template>
      <template #cell-is_active="{ value }">
        <StatusBadge :status="value ? 'active' : 'inactive'" :label="value ? 'Active' : 'Inactive'" />
      </template>
      <template #cell-created_at="{ value }">
        {{ new Date(value).toLocaleDateString() }}
      </template>
      <template #actions="{ row }">
        <div class="flex justify-end gap-2">
          <button @click="openEdit(row)" class="btn btn-sm btn-secondary">Edit</button>
          <button
            @click="toggleActive(row)"
            :class="['btn btn-sm', row.is_active ? 'btn-secondary' : 'btn-primary']"
          >
            {{ row.is_active ? 'Deactivate' : 'Activate' }}
          </button>
          <button @click="confirmDelete(row)" class="btn btn-sm btn-danger">Delete</button>
        </div>
      </template>
    </DataTable>

    <!-- Create/Edit Modal -->
    <Modal v-model="showModal" :title="editingUser ? 'Edit User' : 'Create User'" size="md">
      <form @submit.prevent="handleSave" class="space-y-4">
        <div v-if="!editingUser">
          <label class="label">Username *</label>
          <input v-model="form.username" type="text" class="input" required />
        </div>
        <div>
          <label class="label">Email *</label>
          <input v-model="form.email" type="email" class="input" required />
        </div>
        <div>
          <label class="label">{{ editingUser ? 'New Password (leave blank to keep)' : 'Password *' }}</label>
          <input v-model="form.password" type="password" class="input" :required="!editingUser" />
        </div>
        <div>
          <label class="label">Role *</label>
          <select v-model="form.role" class="input" required>
            <option value="admin">Administrator</option>
            <option value="clinic_staff">Clinic Staff</option>
            <option value="catalog_manager">Catalog Manager</option>
            <option value="end_user">End User (Patient)</option>
          </select>
        </div>
        <div v-if="saveError" class="text-sm text-red-600">{{ saveError }}</div>
      </form>
      <template #footer>
        <button @click="showModal = false" class="btn-secondary">Cancel</button>
        <button @click="handleSave" :disabled="saving" class="btn-primary">
          {{ saving ? 'Saving...' : (editingUser ? 'Update User' : 'Create User') }}
        </button>
      </template>
    </Modal>

    <!-- Delete Confirm -->
    <Modal v-model="showDelete" title="Confirm Delete" size="sm">
      <p class="text-slate-600">Delete user <strong>{{ selectedUser?.username }}</strong>? This cannot be undone.</p>
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
import api from '../api/index.js'
import DataTable from '../components/DataTable.vue'
import StatusBadge from '../components/StatusBadge.vue'
import Modal from '../components/Modal.vue'

const props = defineProps({
  filterRole: { type: String, default: '' },
})

const users = ref([])
const loading = ref(true)
const showModal = ref(false)
const showDelete = ref(false)
const saving = ref(false)
const deleting = ref(false)
const saveError = ref('')
const editingUser = ref(null)
const selectedUser = ref(null)

const form = ref({ username: '', email: '', password: '', role: 'end_user' })

const displayUsers = computed(() => {
  if (!props.filterRole) return users.value
  return users.value.filter(u => u.role === props.filterRole)
})

const columns = [
  { key: 'id', label: 'ID' },
  { key: 'username', label: 'Username' },
  { key: 'email', label: 'Email' },
  { key: 'role', label: 'Role' },
  { key: 'is_active', label: 'Status' },
  { key: 'created_at', label: 'Created' },
]

function formatRole(role) {
  const map = { admin: 'Administrator', clinic_staff: 'Clinic Staff', catalog_manager: 'Catalog Manager', end_user: 'End User' }
  return map[role] || role
}

async function fetchUsers() {
  loading.value = true
  try {
    const res = await api.get('/users')
    users.value = res.data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingUser.value = null
  form.value = { username: '', email: '', password: '', role: props.filterRole || 'end_user' }
  showModal.value = true
}

function openEdit(user) {
  editingUser.value = user
  form.value = { username: user.username, email: user.email, password: '', role: user.role }
  showModal.value = true
}

async function handleSave() {
  saveError.value = ''
  saving.value = true
  try {
    if (editingUser.value) {
      const payload = { email: form.value.email, role: form.value.role }
      if (form.value.password) payload.password = form.value.password
      await api.put(`/users/${editingUser.value.id}`, payload)
    } else {
      await api.post('/users', form.value)
    }
    showModal.value = false
    await fetchUsers()
  } catch (err) {
    saveError.value = err.response?.data?.detail || 'Failed to save user.'
  } finally {
    saving.value = false
  }
}

async function toggleActive(user) {
  await api.put(`/users/${user.id}`, { is_active: !user.is_active })
  await fetchUsers()
}

function confirmDelete(user) {
  selectedUser.value = user
  showDelete.value = true
}

async function handleDelete() {
  deleting.value = true
  try {
    await api.delete(`/users/${selectedUser.value.id}`)
    showDelete.value = false
    await fetchUsers()
  } finally {
    deleting.value = false
  }
}

onMounted(fetchUsers)
</script>
