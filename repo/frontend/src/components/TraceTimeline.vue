<template>
  <div class="flow-root">
    <ul class="-mb-8">
      <li v-for="(event, index) in events" :key="event.id">
        <div class="relative pb-8">
          <!-- Connector line -->
          <span
            v-if="index < events.length - 1"
            class="absolute top-4 left-4 -ml-px h-full w-0.5 bg-slate-200"
            aria-hidden="true"
          />
          <div class="relative flex space-x-3">
            <!-- Icon -->
            <div>
              <span :class="['h-8 w-8 rounded-full flex items-center justify-center ring-8 ring-white', iconBg(event.event_type)]">
                <component :is="iconForType(event.event_type)" class="h-4 w-4 text-white" />
              </span>
            </div>
            <!-- Content -->
            <div class="flex min-w-0 flex-1 justify-between space-x-4 pt-1.5">
              <div>
                <p class="text-sm font-semibold text-slate-900 capitalize">
                  {{ event.event_type }}
                  <span v-if="event.location" class="font-normal text-slate-500">
                    at {{ event.location }}
                  </span>
                </p>
                <p v-if="event.notes" class="mt-0.5 text-sm text-slate-500">{{ event.notes }}</p>
              </div>
              <div class="whitespace-nowrap text-right text-sm text-slate-500">
                {{ formatDate(event.timestamp) }}
              </div>
            </div>
          </div>
        </div>
      </li>
    </ul>
    <p v-if="!events.length" class="text-center text-slate-400 text-sm py-8">
      No trace events recorded yet.
    </p>
  </div>
</template>

<script setup>
import { h } from 'vue'

defineProps({
  events: {
    type: Array,
    default: () => [],
  },
})

function formatDate(dateStr) {
  return new Date(dateStr).toLocaleString()
}

function iconBg(type) {
  const map = {
    harvested: 'bg-lime-500',
    processed: 'bg-orange-500',
    packaged: 'bg-purple-500',
    shipped: 'bg-blue-500',
    received: 'bg-green-500',
  }
  return map[type] || 'bg-slate-400'
}

function iconForType(type) {
  // Return SVG icons as render functions
  const icons = {
    harvested: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z' })
    ]),
    processed: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z' })
    ]),
    packaged: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4' })
    ]),
    shipped: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17a2 2 0 104 0m-4 0a2 2 0 114 0m6 0a2 2 0 104 0m-4 0a2 2 0 114 0' })
    ]),
    received: () => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
      h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z' })
    ]),
  }
  return icons[type] || (() => h('svg', { fill: 'none', viewBox: '0 0 24 24', stroke: 'currentColor' }, [
    h('path', { 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'stroke-width': '2', d: 'M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z' })
  ]))
}
</script>
