<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Message Center</h1>
        <p class="text-slate-500 text-sm mt-1">Encrypted messages and conversation threads</p>
      </div>
      <div class="flex gap-2">
        <button @click="openCompose" class="btn-primary">+ Compose</button>
        <button @click="openNewThread" class="btn-secondary">+ New Thread</button>
      </div>
    </div>

    <!-- Mode tabs -->
    <div class="flex gap-1 mb-6 border-b border-slate-200">
      <button v-for="tab in tabs" :key="tab.key" @click="activeMode = tab.key"
        :class="['px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
          activeMode === tab.key ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700']">
        {{ tab.label }}
        <span v-if="tab.key === 'inbox' && directUnread > 0"
          class="ml-1.5 bg-blue-100 text-blue-700 text-xs rounded-full px-1.5 py-0.5">{{ directUnread }}</span>
        <span v-if="tab.key === 'threads' && threadUnread > 0"
          class="ml-1.5 bg-blue-100 text-blue-700 text-xs rounded-full px-1.5 py-0.5">{{ threadUnread }}</span>
      </button>
    </div>

    <!-- DIRECT MESSAGES -->
    <template v-if="activeMode === 'inbox' || activeMode === 'sent'">
      <div v-if="directLoading" class="text-center py-16 text-slate-400">Loading…</div>
      <div v-else-if="directLoadError" class="text-center py-16 text-red-500">{{ directLoadError }}</div>
      <div v-else-if="!currentDirect.length" class="text-center py-16 text-slate-400">No messages.</div>
      <div v-else class="space-y-1">
        <div v-for="msg in currentDirect" :key="msg.id"
          @click="openDirect(msg)"
          :class="['flex items-center gap-4 p-4 rounded-lg border cursor-pointer transition-colors',
            !msg.is_read && activeMode === 'inbox'
              ? 'bg-blue-50 border-blue-200 hover:bg-blue-100'
              : 'bg-white border-slate-200 hover:bg-slate-50']">
          <div :class="['w-2.5 h-2.5 rounded-full shrink-0',
            !msg.is_read && activeMode === 'inbox' ? 'bg-blue-500' : 'bg-transparent']" />
          <div class="flex-1 min-w-0">
            <p :class="['text-sm truncate', !msg.is_read && activeMode==='inbox' ? 'font-semibold text-slate-900' : 'font-medium text-slate-700']">
              {{ msg.subject }}
            </p>
            <p class="text-xs text-slate-500">
              {{ activeMode === 'inbox' ? 'From #' + msg.sender_id : 'To #' + msg.recipient_id }}
            </p>
          </div>
          <span class="text-xs text-slate-400 shrink-0">{{ formatDate(msg.created_at) }}</span>
          <button @click.stop="deleteDirect(msg)" class="text-slate-300 hover:text-red-500 transition-colors shrink-0">
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
      </div>
    </template>

    <!-- THREADS -->
    <template v-if="activeMode === 'threads'">
      <div v-if="threadsLoading" class="text-center py-16 text-slate-400">Loading…</div>
      <div v-else-if="threadsLoadError" class="text-center py-16 text-red-500">{{ threadsLoadError }}</div>
      <div v-else-if="!threads.length" class="text-center py-16 text-slate-400">No threads yet.</div>
      <div v-else class="space-y-2">
        <div v-for="thread in threads" :key="thread.id"
          @click="openThread(thread)"
          :class="['bg-white border rounded-xl p-4 cursor-pointer hover:shadow-sm transition-shadow',
            thread.unread_count > 0 ? 'border-blue-200' : 'border-slate-200']">
          <div class="flex items-start justify-between gap-3">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="font-semibold text-slate-900 truncate">{{ thread.subject }}</span>
                <span v-if="thread.use_virtual_ids" class="text-xs bg-purple-100 text-purple-700 rounded-full px-1.5 py-0.5">Anonymous</span>
                <span v-if="thread.is_archived" class="text-xs bg-slate-100 text-slate-500 rounded-full px-1.5 py-0.5">Archived</span>
              </div>
              <p class="text-xs text-slate-500">{{ thread.participants?.length ?? 0 }} participants</p>
            </div>
            <div class="text-right shrink-0">
              <div v-if="thread.unread_count > 0"
                class="bg-blue-500 text-white text-xs rounded-full px-1.5 py-0.5 font-bold inline-block mb-1">
                {{ thread.unread_count }}
              </div>
              <div class="text-xs text-slate-400">{{ formatDate(thread.updated_at) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- PREFERENCES tab -->
    <template v-if="activeMode === 'preferences'">
      <div class="max-w-lg bg-white rounded-xl border border-slate-200 p-6">
        <h2 class="text-base font-semibold text-slate-900 mb-4">Notification Preferences</h2>
        <div v-if="prefLoading" class="text-slate-400 text-sm">Loading…</div>
        <div v-else-if="prefs" class="space-y-3">
          <label v-for="(label, key) in prefLabels" :key="key" class="flex items-center gap-3 cursor-pointer">
            <input v-model="prefs[key]" type="checkbox" class="rounded text-blue-600" @change="savePrefs" />
            <span class="text-sm text-slate-700">{{ label }}</span>
          </label>
        </div>
        <p v-if="prefSaved" class="text-green-600 text-sm mt-3">Preferences saved.</p>
      </div>
    </template>

    <!-- View Direct Message Modal -->
    <Modal v-model="showDirect" :title="selectedDirect?.subject" size="lg">
      <div v-if="loadingDirect" class="py-8 text-center text-slate-400">Decrypting…</div>
      <div v-else-if="directDetailError" class="py-8 text-center text-red-500">{{ directDetailError }}</div>
      <div v-else-if="directDetail" class="space-y-4">
        <div class="flex gap-6 text-sm text-slate-500">
          <span>From: <span class="font-medium text-slate-800">#{{ directDetail.sender_id }}</span></span>
          <span>To: <span class="font-medium text-slate-800">#{{ directDetail.recipient_id }}</span></span>
          <span>{{ formatDate(directDetail.created_at) }}</span>
        </div>
        <div class="bg-slate-50 rounded-lg p-4 text-sm text-slate-800 whitespace-pre-wrap min-h-24">
          {{ directDetail.body }}
        </div>
      </div>
      <template #footer>
        <button @click="showDirect = false" class="btn-secondary">Close</button>
        <button @click="replyTo(directDetail)" class="btn-primary">Reply</button>
      </template>
    </Modal>

    <!-- Thread View Modal -->
    <Modal v-model="showThread" :title="selectedThread?.subject" size="xl">
      <div class="flex flex-col h-[500px]">
        <!-- Messages -->
        <div class="flex-1 overflow-y-auto space-y-3 mb-4" ref="threadScrollEl">
          <div v-if="threadMsgsLoading" class="text-center py-8 text-slate-400">Loading…</div>
          <div v-for="msg in threadMessages" :key="msg.id"
            :class="['flex gap-3', msg.sender_id === authStore.user?.id ? 'flex-row-reverse' : '']">
            <div class="shrink-0 w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-700 text-xs font-bold">
              {{ msg.sender_alias?.slice(0, 2).toUpperCase() ?? '#' + msg.sender_id }}
            </div>
            <div :class="['max-w-[70%] rounded-xl px-4 py-2.5 text-sm',
              msg.is_system_message ? 'bg-slate-100 text-slate-500 text-xs italic' :
              msg.sender_id === authStore.user?.id ? 'bg-blue-600 text-white' : 'bg-white border border-slate-200 text-slate-800']">
              <p class="whitespace-pre-wrap">{{ msg.body }}</p>
              <p class="text-xs opacity-60 mt-1">{{ formatDateFull(msg.created_at) }}
                <span v-if="selectedThread?.use_virtual_ids && msg.sender_alias" class="ml-1">[{{ msg.sender_alias }}]</span>
              </p>
            </div>
          </div>
        </div>
        <!-- Compose -->
        <div class="flex gap-2 border-t border-slate-200 pt-3">
          <textarea v-model="threadReplyBody" class="input flex-1 resize-none" rows="2"
            placeholder="Type a message…" @keydown.ctrl.enter="sendThreadMessage" />
          <button @click="sendThreadMessage" :disabled="!threadReplyBody.trim() || sendingMsg"
            class="btn-primary px-4 self-end">
            {{ sendingMsg ? '…' : 'Send' }}
          </button>
        </div>
      </div>
      <template #footer>
        <div class="flex gap-2">
          <button v-if="authStore.isRole('admin','clinic_staff') && selectedThread?.use_virtual_ids"
            @click="resolveAlias" class="btn-secondary text-xs">View Real IDs</button>
          <button @click="archiveThread" v-if="!selectedThread?.is_archived" class="btn-secondary text-xs">Archive</button>
        </div>
        <button @click="showThread = false" class="btn-secondary">Close</button>
      </template>
    </Modal>

    <!-- Compose Direct Modal -->
    <Modal v-model="showCompose" title="New Message" size="md">
      <form @submit.prevent="handleSend" class="space-y-4">
        <div>
          <label class="label">Recipient *</label>
          <input v-model.number="composeForm.recipient_id" type="number" class="input" required placeholder="User ID" />
        </div>
        <div>
          <label class="label">Subject *</label>
          <input v-model="composeForm.subject" type="text" class="input" required />
        </div>
        <div>
          <label class="label">Message (encrypted at rest)</label>
          <textarea v-model="composeForm.body" class="input" rows="5" required />
        </div>
        <div v-if="sendError" class="text-sm text-red-600">{{ sendError }}</div>
      </form>
      <template #footer>
        <button @click="showCompose = false" class="btn-secondary">Cancel</button>
        <button @click="handleSend" :disabled="sending" class="btn-primary">{{ sending ? 'Sending…' : 'Send' }}</button>
      </template>
    </Modal>

    <!-- New Thread Modal -->
    <Modal v-model="showNewThread" title="New Thread" size="md">
      <form @submit.prevent="handleNewThread" class="space-y-4">
        <div>
          <label class="label">Subject *</label>
          <input v-model="threadForm.subject" type="text" class="input" required />
        </div>
        <div>
          <label class="label">Participants (User IDs, comma-separated) *</label>
          <input v-model="threadForm.participantIds" type="text" class="input" placeholder="1,5,12" required />
        </div>
        <div>
          <label class="label">Order ID (optional)</label>
          <input v-model.number="threadForm.order_id" type="number" class="input" />
        </div>
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <input v-model="threadForm.use_virtual_ids" type="checkbox" class="rounded" />
          Anonymous relay (hide real user IDs from participants)
        </label>
        <div v-if="threadError" class="text-sm text-red-600">{{ threadError }}</div>
      </form>
      <template #footer>
        <button @click="showNewThread = false" class="btn-secondary">Cancel</button>
        <button @click="handleNewThread" :disabled="creatingThread" class="btn-primary">
          {{ creatingThread ? 'Creating…' : 'Create Thread' }}
        </button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import api from '../api/index.js'
import Modal from '../components/Modal.vue'
import { useAuthStore } from '../stores/auth.js'
import { useNotificationStore } from '../stores/notifications.js'

const authStore = useAuthStore()
const notifStore = useNotificationStore()

const tabs = [
  { key: 'inbox', label: 'Inbox' },
  { key: 'sent', label: 'Sent' },
  { key: 'threads', label: 'Threads' },
  { key: 'preferences', label: 'Preferences' },
]
const activeMode = ref('inbox')

// Direct
const inbox = ref([])
const sent = ref([])
const directLoading = ref(false)
const directLoadError = ref('')
const showDirect = ref(false)
const selectedDirect = ref(null)
const directDetail = ref(null)
const loadingDirect = ref(false)
const directDetailError = ref('')
const showCompose = ref(false)
const sending = ref(false)
const sendError = ref('')
const composeForm = ref({ recipient_id: '', subject: '', body: '' })

const directUnread = computed(() => inbox.value.filter(m => !m.is_read).length)
const currentDirect = computed(() => activeMode.value === 'inbox' ? inbox.value : sent.value)

// Threads
const threads = ref([])
const threadsLoading = ref(false)
const threadsLoadError = ref('')
const showThread = ref(false)
const selectedThread = ref(null)
const threadMessages = ref([])
const threadMsgsLoading = ref(false)
const threadReplyBody = ref('')
const sendingMsg = ref(false)
const showNewThread = ref(false)
const creatingThread = ref(false)
const threadError = ref('')
const threadForm = ref({ subject: '', participantIds: '', order_id: null, use_virtual_ids: false })
const threadScrollEl = ref(null)

const threadUnread = computed(() => threads.value.reduce((s, t) => s + (t.unread_count || 0), 0))

// Preferences
const prefs = ref(null)
const prefLoading = ref(false)
const prefSaved = ref(false)
const prefLabels = {
  notify_order_accepted: 'Order accepted',
  notify_order_arrived: 'Order arrived',
  notify_order_completed: 'Order completed',
  notify_order_exception: 'Order exception',
  notify_new_message: 'New direct message',
  notify_thread_reply: 'Thread reply',
  notify_system: 'System notifications',
  notify_info: 'Info notifications',
}

function formatDate(d) { return d ? new Date(d).toLocaleDateString() : '' }
function formatDateFull(d) { return d ? new Date(d).toLocaleString() : '' }

async function fetchDirect() {
  directLoading.value = true
  directLoadError.value = ''
  try {
    const [inboxRes, sentRes] = await Promise.all([api.get('/messages/inbox'), api.get('/messages/sent')])
    inbox.value = inboxRes.data
    sent.value = sentRes.data
  } catch (err) {
    directLoadError.value = err.response?.data?.detail || 'Failed to load messages.'
  } finally { directLoading.value = false }
}

async function fetchThreads() {
  threadsLoading.value = true
  threadsLoadError.value = ''
  try {
    const res = await api.get('/messages/threads')
    threads.value = res.data
  } catch (err) {
    threadsLoadError.value = err.response?.data?.detail || 'Failed to load threads.'
  } finally { threadsLoading.value = false }
}

async function fetchPrefs() {
  prefLoading.value = true
  try {
    const res = await api.get('/notifications/preferences/me')
    prefs.value = res.data
  } finally { prefLoading.value = false }
}

async function savePrefs() {
  await api.put('/notifications/preferences/me', prefs.value)
  prefSaved.value = true
  setTimeout(() => prefSaved.value = false, 2000)
}

async function openDirect(msg) {
  selectedDirect.value = msg
  showDirect.value = true
  loadingDirect.value = true
  directDetailError.value = ''
  try {
    const res = await api.get(`/messages/${msg.id}`)
    directDetail.value = res.data
    if (!msg.is_read) { msg.is_read = true; await api.patch(`/messages/${msg.id}/read`) }
  } catch (err) {
    directDetailError.value = err.response?.data?.detail || 'Failed to load message. The content may be unavailable.'
  } finally { loadingDirect.value = false }
}

function openCompose() { composeForm.value = { recipient_id: '', subject: '', body: '' }; sendError.value = ''; showCompose.value = true }

function replyTo(msg) {
  showDirect.value = false
  composeForm.value = { recipient_id: msg.sender_id, subject: `Re: ${msg.subject}`, body: '' }
  showCompose.value = true
}

async function handleSend() {
  sendError.value = ''
  sending.value = true
  try {
    await api.post('/messages', { ...composeForm.value, recipient_id: Number(composeForm.value.recipient_id) })
    showCompose.value = false
    await fetchDirect()
  } catch (err) { sendError.value = err.response?.data?.detail || 'Failed to send.' }
  finally { sending.value = false }
}

async function deleteDirect(msg) {
  if (!confirm('Delete this message?')) return
  await api.delete(`/messages/${msg.id}`)
  await fetchDirect()
}

async function openThread(thread) {
  selectedThread.value = thread
  showThread.value = true
  threadMsgsLoading.value = true
  threadReplyBody.value = ''
  try {
    const res = await api.get(`/messages/threads/${thread.id}`)
    threadMessages.value = res.data.messages || []
    thread.unread_count = 0
    await api.patch(`/messages/threads/${thread.id}/read`)
    await nextTick()
    if (threadScrollEl.value) threadScrollEl.value.scrollTop = threadScrollEl.value.scrollHeight
  } finally { threadMsgsLoading.value = false }
}

async function sendThreadMessage() {
  if (!threadReplyBody.value.trim() || sendingMsg.value) return
  sendingMsg.value = true
  try {
    const res = await api.post(`/messages/threads/${selectedThread.value.id}/messages`, { body: threadReplyBody.value })
    threadMessages.value.push(res.data)
    threadReplyBody.value = ''
    await nextTick()
    if (threadScrollEl.value) threadScrollEl.value.scrollTop = threadScrollEl.value.scrollHeight
  } finally { sendingMsg.value = false }
}

async function archiveThread() {
  await api.patch(`/messages/threads/${selectedThread.value.id}/archive`)
  selectedThread.value.is_archived = true
}

async function resolveAlias() {
  // Show mapping of virtual -> real IDs for admin
  const aliases = {}
  for (const msg of threadMessages.value) {
    if (msg.sender_alias && !aliases[msg.sender_alias]) {
      try {
        const res = await api.get(`/messages/threads/${selectedThread.value.id}/resolve-alias/${msg.sender_alias}`)
        aliases[msg.sender_alias] = res.data
      } catch { aliases[msg.sender_alias] = 'Unknown' }
    }
  }
  alert(Object.entries(aliases).map(([a, v]) => `${a} → User #${v.user_id || v}`).join('\n'))
}

function openNewThread() {
  threadForm.value = { subject: '', participantIds: '', order_id: null, use_virtual_ids: false }
  threadError.value = ''
  showNewThread.value = true
}

async function handleNewThread() {
  threadError.value = ''
  creatingThread.value = true
  try {
    const ids = threadForm.value.participantIds.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n))
    await api.post('/messages/threads', {
      subject: threadForm.value.subject,
      participant_ids: ids,
      order_id: threadForm.value.order_id || null,
      use_virtual_ids: threadForm.value.use_virtual_ids,
    })
    showNewThread.value = false
    await fetchThreads()
    activeMode.value = 'threads'
  } catch (err) { threadError.value = err.response?.data?.detail || 'Failed to create thread.' }
  finally { creatingThread.value = false }
}

onMounted(async () => {
  await Promise.all([fetchDirect(), fetchThreads(), fetchPrefs()])
})
</script>
