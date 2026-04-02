<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Quick Views</h1>
        <p class="text-slate-500 text-sm mt-1">
          {{ qvStore.views.length }}/{{ qvStore.MAX_QUICK_VIEWS }} saved items
        </p>
      </div>
      <button v-if="qvStore.views.length" @click="clearAll" class="btn-secondary text-sm text-red-600 border-red-200 hover:bg-red-50">
        Clear All
      </button>
    </div>

    <!-- Empty state -->
    <div v-if="!qvStore.views.length" class="text-center py-20 bg-white rounded-xl border border-slate-200">
      <svg class="w-12 h-12 mx-auto text-slate-300 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
      </svg>
      <p class="text-slate-500 mb-2">No quick views saved yet</p>
      <p class="text-sm text-slate-400">Hit ☆ Save on any package or catalog item to add it here</p>
      <div class="flex justify-center gap-3 mt-4">
        <RouterLink to="/packages" class="btn-primary text-sm">Browse Packages</RouterLink>
        <RouterLink to="/catalog" class="btn-secondary text-sm">Browse Catalog</RouterLink>
      </div>
    </div>

    <!-- Grouped by type -->
    <div v-else>
      <div v-for="(group, type) in grouped" :key="type" class="mb-8">
        <h2 class="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3 flex items-center gap-2">
          <span>{{ typeLabel(type) }}</span>
          <span class="bg-slate-100 text-slate-500 rounded-full text-xs px-1.5 py-0.5">{{ group.length }}</span>
        </h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <div v-for="view in group" :key="view.id + view.type"
            class="bg-white rounded-xl border border-slate-200 p-4 hover:shadow-sm transition-shadow flex flex-col">
            <div class="flex items-start justify-between gap-2 mb-3">
              <div>
                <p class="font-semibold text-slate-900 text-sm leading-tight">{{ view.label }}</p>
                <p class="text-xs text-slate-400 mt-0.5">Saved {{ formatDate(view.savedAt) }}</p>
              </div>
              <button @click="qvStore.remove(view.id, view.type)"
                class="text-slate-300 hover:text-red-400 transition-colors shrink-0">
                <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fill-rule="evenodd"
                    d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                    clip-rule="evenodd" />
                </svg>
              </button>
            </div>

            <!-- Meta chips -->
            <div class="flex flex-wrap gap-1.5 mb-3">
              <span v-if="view.meta?.price"
                class="text-xs bg-blue-50 text-blue-700 rounded-full px-2 py-0.5 font-semibold">
                ${{ Number(view.meta.price).toFixed(2) }}
              </span>
              <span v-if="view.meta?.validity"
                class="text-xs bg-slate-100 text-slate-600 rounded-full px-2 py-0.5">
                {{ view.meta.validity }}d validity
              </span>
              <span v-if="view.meta?.category"
                class="text-xs bg-green-50 text-green-700 rounded-full px-2 py-0.5">
                {{ view.meta.category }}
              </span>
              <span v-if="view.meta?.status"
                class="text-xs bg-amber-50 text-amber-700 rounded-full px-2 py-0.5">
                {{ view.meta.status }}
              </span>
            </div>

            <RouterLink :to="view.route" class="mt-auto btn-secondary text-xs text-center">
              View →
            </RouterLink>
          </div>
        </div>
      </div>
    </div>

    <!-- Capacity bar -->
    <div v-if="qvStore.views.length" class="mt-8 bg-slate-50 rounded-xl p-4 border border-slate-200">
      <div class="flex items-center justify-between text-xs text-slate-500 mb-1.5">
        <span>Storage used</span>
        <span>{{ qvStore.views.length }} / {{ qvStore.MAX_QUICK_VIEWS }}</span>
      </div>
      <div class="h-2 bg-slate-200 rounded-full overflow-hidden">
        <div class="h-full rounded-full transition-all duration-500"
          :class="qvStore.views.length >= qvStore.MAX_QUICK_VIEWS ? 'bg-red-500' : 'bg-blue-500'"
          :style="`width: ${(qvStore.views.length / qvStore.MAX_QUICK_VIEWS) * 100}%`" />
      </div>
      <p v-if="qvStore.views.length >= qvStore.MAX_QUICK_VIEWS"
        class="text-xs text-red-600 mt-1">Maximum reached. Remove items to save new ones.</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useQuickViewStore } from '../stores/quickviews.js'

const qvStore = useQuickViewStore()

const grouped = computed(() => {
  const g = {}
  for (const v of qvStore.views) {
    if (!g[v.type]) g[v.type] = []
    g[v.type].push(v)
  }
  return g
})

function typeLabel(t) {
  return { package: 'Exam Packages', catalog: 'Catalog Items', review: 'Reviews' }[t] ?? t
}

function formatDate(d) { return d ? new Date(d).toLocaleDateString() : '' }

function clearAll() {
  if (confirm('Clear all quick views? This cannot be undone.')) qvStore.clear()
}
</script>
