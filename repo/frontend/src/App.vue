<template>
  <div class="min-h-screen bg-slate-50">
    <!-- Offline banner -->
    <div v-if="!offlineStore.isOnline"
      class="fixed top-0 left-0 right-0 z-[100] bg-amber-500 text-white text-center text-sm py-1.5 font-medium">
      ⚠ You are offline — viewing cached data
    </div>

    <NavBar v-if="authStore.isAuthenticated" />
    <main :class="[authStore.isAuthenticated ? 'pt-16' : '', !offlineStore.isOnline ? 'mt-8' : '']">
      <RouterView />
    </main>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { RouterView } from 'vue-router'
import NavBar from './components/NavBar.vue'
import { useAuthStore } from './stores/auth.js'
import { useNotificationStore } from './stores/notifications.js'
import { useOfflineStore } from './stores/offline.js'

const authStore = useAuthStore()
const notifStore = useNotificationStore()
const offlineStore = useOfflineStore()

onMounted(async () => {
  if (authStore.isAuthenticated) {
    await authStore.init()
    notifStore.startPolling(30000)
  }
})

onUnmounted(() => notifStore.stopPolling())
</script>
