<template>
  <slot v-if="hasAccess" />
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth.js'

const props = defineProps({
  roles: {
    type: Array,
    required: true,
  },
})

const authStore = useAuthStore()

const hasAccess = computed(() => {
  if (!authStore.userRole) return false
  return props.roles.includes(authStore.userRole)
})
</script>
