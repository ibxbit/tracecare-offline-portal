<template>
  <div class="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="mb-6">
      <h1 class="text-2xl font-bold text-slate-900">My Profile</h1>
      <p class="text-slate-500 text-sm mt-1">Update your account information</p>
    </div>

    <div class="card">
      <!-- Profile Header -->
      <div class="flex items-center gap-4 mb-6 pb-6 border-b border-slate-200">
        <div class="w-16 h-16 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 font-bold text-2xl">
          {{ authStore.user?.username?.charAt(0).toUpperCase() }}
        </div>
        <div>
          <h2 class="text-xl font-semibold text-slate-900">{{ authStore.user?.username }}</h2>
          <div class="flex items-center gap-2 mt-1">
            <StatusBadge :status="authStore.userRole" :label="formatRole(authStore.userRole)" />
            <span class="text-sm text-slate-500">{{ authStore.user?.email }}</span>
          </div>
        </div>
      </div>

      <!-- Edit Form -->
      <form @submit.prevent="handleSave" class="space-y-5">
        <div>
          <label class="label">Username</label>
          <input type="text" :value="authStore.user?.username" class="input bg-slate-50 cursor-not-allowed" disabled />
          <p class="text-xs text-slate-400 mt-1">Username cannot be changed.</p>
        </div>

        <div>
          <label class="label">Email Address</label>
          <input v-model="form.email" type="email" class="input" />
        </div>

        <div>
          <label class="label">New Password</label>
          <input v-model="form.password" type="password" class="input" placeholder="Leave blank to keep current password" />
        </div>

        <div>
          <label class="label">Confirm New Password</label>
          <input v-model="form.confirmPassword" type="password" class="input" placeholder="Confirm new password" />
        </div>

        <div v-if="error" class="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700">
          {{ error }}
        </div>
        <div v-if="success" class="rounded-lg bg-green-50 border border-green-200 p-3 text-sm text-green-700">
          Profile updated successfully!
        </div>

        <div class="flex gap-3 pt-2">
          <button type="submit" :disabled="saving" class="btn-primary">
            {{ saving ? 'Saving...' : 'Save Changes' }}
          </button>
          <button type="button" @click="resetForm" class="btn-secondary">Reset</button>
        </div>
      </form>
    </div>

    <!-- Account Info Card -->
    <div class="card mt-6">
      <h3 class="text-lg font-semibold text-slate-800 mb-4">Account Information</h3>
      <dl class="grid grid-cols-2 gap-4 text-sm">
        <div>
          <dt class="text-slate-500">Account ID</dt>
          <dd class="font-medium text-slate-800">#{{ authStore.user?.id }}</dd>
        </div>
        <div>
          <dt class="text-slate-500">Role</dt>
          <dd class="font-medium text-slate-800">{{ formatRole(authStore.userRole) }}</dd>
        </div>
        <div>
          <dt class="text-slate-500">Status</dt>
          <dd><StatusBadge :status="authStore.user?.is_active ? 'active' : 'inactive'" :label="authStore.user?.is_active ? 'Active' : 'Inactive'" /></dd>
        </div>
        <div>
          <dt class="text-slate-500">Member Since</dt>
          <dd class="font-medium text-slate-800">
            {{ authStore.user?.created_at ? new Date(authStore.user.created_at).toLocaleDateString() : '-' }}
          </dd>
        </div>
      </dl>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth.js'
import StatusBadge from '../components/StatusBadge.vue'
import api from '../api/index.js'

const authStore = useAuthStore()
const saving = ref(false)
const error = ref('')
const success = ref(false)

const form = ref({ email: '', password: '', confirmPassword: '' })

function formatRole(role) {
  const map = {
    admin: 'Administrator',
    clinic_staff: 'Clinic Staff',
    catalog_manager: 'Catalog Manager',
    end_user: 'End User',
  }
  return map[role] || role
}

function resetForm() {
  form.value = { email: authStore.user?.email || '', password: '', confirmPassword: '' }
  error.value = ''
  success.value = false
}

async function handleSave() {
  error.value = ''
  success.value = false

  if (form.value.password && form.value.password !== form.value.confirmPassword) {
    error.value = 'Passwords do not match.'
    return
  }

  saving.value = true
  try {
    const payload = {}
    if (form.value.email && form.value.email !== authStore.user.email) {
      payload.email = form.value.email
    }
    if (form.value.password) {
      payload.password = form.value.password
    }
    if (Object.keys(payload).length === 0) {
      error.value = 'No changes to save.'
      return
    }
    await api.put('/users/me', payload)
    await authStore.fetchUser()
    success.value = true
    form.value.password = ''
    form.value.confirmPassword = ''
  } catch (err) {
    error.value = err.response?.data?.detail || 'Failed to update profile.'
  } finally {
    saving.value = false
  }
}

onMounted(resetForm)
</script>
