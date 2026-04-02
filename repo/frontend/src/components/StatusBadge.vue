<template>
  <span :class="['badge', colorClass]">
    {{ label || status }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, required: true },
  label: { type: String, default: '' },
  type: { type: String, default: 'status' },
})

const colorMap = {
  // Exam status
  scheduled: 'bg-blue-100 text-blue-800',
  in_progress: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  cancelled: 'bg-red-100 text-red-800',
  // Trace events
  harvested: 'bg-lime-100 text-lime-800',
  processed: 'bg-orange-100 text-orange-800',
  packaged: 'bg-purple-100 text-purple-800',
  shipped: 'bg-blue-100 text-blue-800',
  received: 'bg-green-100 text-green-800',
  // Roles
  admin: 'bg-red-100 text-red-800',
  clinic_staff: 'bg-blue-100 text-blue-800',
  catalog_manager: 'bg-purple-100 text-purple-800',
  end_user: 'bg-slate-100 text-slate-800',
  // Boolean
  true: 'bg-green-100 text-green-800',
  false: 'bg-slate-100 text-slate-500',
  // Generic
  active: 'bg-green-100 text-green-800',
  inactive: 'bg-slate-100 text-slate-500',
  published: 'bg-green-100 text-green-800',
  draft: 'bg-yellow-100 text-yellow-800',
  // Products
  product: 'bg-blue-100 text-blue-800',
  exam_type: 'bg-purple-100 text-purple-800',
}

const colorClass = computed(() => {
  const key = String(props.status).toLowerCase()
  return colorMap[key] || 'bg-slate-100 text-slate-700'
})
</script>
