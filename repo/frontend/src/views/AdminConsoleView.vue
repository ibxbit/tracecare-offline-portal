<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Admin Console</h1>
        <p class="text-slate-500 text-sm mt-1">Site rules, tasks, proxy pool, API keys, exports</p>
      </div>
      <!-- Status badge -->
      <div v-if="systemStatus" :class="['flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium',
        systemStatus.status === 'ok' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700']">
        <div :class="['w-2 h-2 rounded-full', systemStatus.status === 'ok' ? 'bg-green-500' : 'bg-red-500']" />
        System {{ systemStatus.status }}
      </div>
    </div>

    <!-- System stat cards -->
    <div v-if="systemStatus" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
      <div v-for="stat in statCards" :key="stat.label"
        class="bg-white rounded-xl border border-slate-200 p-4 text-center">
        <div class="text-2xl font-bold text-slate-900">{{ stat.value }}</div>
        <div class="text-xs text-slate-500 mt-0.5">{{ stat.label }}</div>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex gap-1 mb-6 border-b border-slate-200">
      <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
        :class="['px-4 py-2 text-sm font-medium transition-colors border-b-2 -mb-px',
          activeTab === tab.key ? 'border-blue-500 text-blue-600' : 'border-transparent text-slate-500 hover:text-slate-700']">
        {{ tab.label }}
      </button>
    </div>

    <!-- SITE RULES -->
    <template v-if="activeTab === 'rules'">
      <div class="flex justify-end mb-4">
        <button @click="openCreateRule" class="btn-primary">+ New Rule</button>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-slate-200">
            <tr>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Name</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Value</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Type</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Status</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="rulesLoading"><td colspan="5" class="text-center py-8 text-slate-400">Loading…</td></tr>
            <tr v-for="rule in rules" :key="rule.id" class="hover:bg-slate-50">
              <td class="px-4 py-3 font-mono text-xs text-slate-700">{{ rule.name }}</td>
              <td class="px-4 py-3 text-slate-600 max-w-xs truncate">{{ rule.value }}</td>
              <td class="px-4 py-3 text-xs text-slate-500">{{ rule.value_type }}</td>
              <td class="px-4 py-3">
                <span :class="['text-xs px-2 py-0.5 rounded-full font-medium',
                  rule.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
                  {{ rule.is_active ? 'Active' : 'Inactive' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex gap-2">
                  <button @click="editRule(rule)" class="text-xs text-blue-600 hover:underline">Edit</button>
                  <button @click="toggleRule(rule)" class="text-xs text-slate-500 hover:underline">Toggle</button>
                  <button @click="deleteRule(rule)" class="text-xs text-red-500 hover:underline">Delete</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- SYSTEM PARAMETERS -->
    <template v-if="activeTab === 'params'">
      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-slate-200">
            <tr>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Key</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Value</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Type</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">R/O</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="paramsLoading"><td colspan="5" class="text-center py-8 text-slate-400">Loading…</td></tr>
            <tr v-for="p in params" :key="p.key" class="hover:bg-slate-50">
              <td class="px-4 py-3 font-mono text-xs text-slate-700">{{ p.key }}</td>
              <td class="px-4 py-3 text-slate-600">{{ p.value }}</td>
              <td class="px-4 py-3 text-xs text-slate-500">{{ p.value_type }}</td>
              <td class="px-4 py-3">
                <span v-if="p.is_readonly" class="text-xs text-slate-400">🔒 Yes</span>
              </td>
              <td class="px-4 py-3">
                <button v-if="!p.is_readonly" @click="editParam(p)" class="text-xs text-blue-600 hover:underline">Edit</button>
                <span v-else class="text-xs text-slate-300">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- TASKS -->
    <template v-if="activeTab === 'tasks'">
      <div class="flex justify-end mb-4 gap-2">
        <button @click="openCreateTask" class="btn-primary">+ New Task</button>
        <a :href="apiBase + '/admin/export/tasks'" target="_blank" class="btn-secondary text-sm">Export CSV</a>
      </div>
      <!-- Status filter -->
      <div class="flex gap-2 mb-4 flex-wrap">
        <button v-for="s in ['', 'pending', 'running', 'completed', 'failed', 'cancelled']" :key="s"
          @click="taskStatusFilter = s; fetchTasks()"
          :class="['text-xs px-3 py-1.5 rounded-full border transition-colors',
            taskStatusFilter === s ? 'bg-blue-600 text-white border-blue-600' : 'border-slate-200 text-slate-600']">
          {{ s || 'All' }}
        </button>
      </div>
      <div class="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <table class="w-full text-sm">
          <thead class="bg-slate-50 border-b border-slate-200">
            <tr>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Task</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Type</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Status</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Priority</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Source</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Created</th>
              <th class="text-left px-4 py-3 font-semibold text-slate-600">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-100">
            <tr v-if="tasksLoading"><td colspan="7" class="text-center py-8 text-slate-400">Loading…</td></tr>
            <tr v-for="task in tasks" :key="task.id" class="hover:bg-slate-50">
              <td class="px-4 py-3 font-medium text-slate-900 max-w-[200px] truncate">{{ task.name }}</td>
              <td class="px-4 py-3 text-xs text-slate-500 font-mono">{{ task.task_type }}</td>
              <td class="px-4 py-3">
                <span :class="['text-xs px-2 py-0.5 rounded-full font-medium', taskStatusColor(task.status)]">
                  {{ task.status }}
                </span>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-1">
                  <div class="h-1.5 rounded-full bg-blue-500" :style="`width: ${task.priority * 10}px`" />
                  <span class="text-xs text-slate-500">{{ task.priority }}</span>
                </div>
              </td>
              <td class="px-4 py-3 text-xs text-slate-500">{{ task.external_system || 'Internal' }}</td>
              <td class="px-4 py-3 text-xs text-slate-400">{{ formatDate(task.created_at) }}</td>
              <td class="px-4 py-3">
                <div class="flex gap-2">
                  <button @click="updateTaskStatus(task, 'running')" v-if="task.status === 'pending'"
                    class="text-xs text-blue-600 hover:underline">Start</button>
                  <button @click="updateTaskStatus(task, 'completed')" v-if="task.status === 'running'"
                    class="text-xs text-green-600 hover:underline">Complete</button>
                  <button @click="cancelTask(task)" v-if="['pending','running'].includes(task.status)"
                    class="text-xs text-red-500 hover:underline">Cancel</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- PROXY POOL -->
    <template v-if="activeTab === 'proxy'">
      <div class="flex justify-end mb-4">
        <button @click="openCreateProxy" class="btn-primary">+ Add Proxy</button>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-if="proxiesLoading" class="col-span-full text-center py-8 text-slate-400">Loading…</div>
        <div v-for="proxy in proxies" :key="proxy.id"
          class="bg-white rounded-xl border border-slate-200 p-4">
          <div class="flex items-start justify-between mb-2">
            <div>
              <p class="font-semibold text-slate-900 text-sm">{{ proxy.label }}</p>
              <p class="text-xs text-slate-500 font-mono">{{ proxy.protocol }}://{{ proxy.host }}:{{ proxy.port }}</p>
            </div>
            <div class="flex flex-col items-end gap-1">
              <span :class="['text-xs px-1.5 py-0.5 rounded-full font-medium',
                proxy.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
                {{ proxy.is_active ? 'Active' : 'Off' }}
              </span>
              <span v-if="proxy.is_healthy !== null"
                :class="['text-xs px-1.5 py-0.5 rounded-full', proxy.is_healthy ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600']">
                {{ proxy.is_healthy ? '✓ Healthy' : '✗ Down' }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-2 text-xs text-slate-400 mb-3">
            <span>Weight: {{ proxy.weight }}</span>
            <span v-if="proxy.region">• {{ proxy.region }}</span>
            <span v-if="proxy.username">• Auth</span>
          </div>
          <div class="flex gap-2">
            <button @click="checkHealth(proxy)" class="text-xs text-blue-600 hover:underline">Health Check</button>
            <button @click="deleteProxy(proxy)" class="text-xs text-red-500 hover:underline">Delete</button>
          </div>
        </div>
      </div>
    </template>

    <!-- API KEYS -->
    <template v-if="activeTab === 'apikeys'">
      <div class="flex justify-end mb-4 gap-2">
        <button @click="openCreateKey" class="btn-primary">+ Issue Key</button>
        <a :href="apiBase + '/admin/export/api-keys'" target="_blank" class="btn-secondary text-sm">Export CSV</a>
      </div>
      <div class="space-y-3">
        <div v-if="keysLoading" class="text-center py-8 text-slate-400">Loading…</div>
        <div v-for="k in apiKeys" :key="k.id"
          class="bg-white rounded-xl border border-slate-200 p-4 flex items-center gap-4">
          <div class="flex-1">
            <div class="flex items-center gap-3 mb-1">
              <p class="font-semibold text-slate-900 text-sm">{{ k.label }}</p>
              <span :class="['text-xs px-1.5 py-0.5 rounded-full font-medium',
                k.is_active ? 'bg-green-100 text-green-700' : 'bg-slate-100 text-slate-500']">
                {{ k.is_active ? 'Active' : 'Inactive' }}
              </span>
            </div>
            <div class="flex gap-4 text-xs text-slate-500">
              <span>System: <span class="font-mono text-slate-700">{{ k.system_name }}</span></span>
              <span>Prefix: <span class="font-mono text-slate-700">{{ k.key_prefix }}…</span></span>
              <span>{{ k.rate_limit_per_minute }} req/min</span>
              <span>Used {{ k.usage_count }}x</span>
              <span v-if="k.last_used_at">Last: {{ formatDate(k.last_used_at) }}</span>
              <span v-if="k.expires_at" :class="isExpired(k.expires_at) ? 'text-red-600' : ''">
                {{ isExpired(k.expires_at) ? 'EXPIRED' : 'Exp: ' + formatDate(k.expires_at) }}
              </span>
            </div>
          </div>
          <div class="flex gap-2 shrink-0">
            <button @click="rotateKey(k)" class="text-xs text-amber-600 hover:underline">Rotate</button>
            <button @click="toggleKey(k)" class="text-xs text-slate-500 hover:underline">
              {{ k.is_active ? 'Disable' : 'Enable' }}
            </button>
            <button @click="deleteKey(k)" class="text-xs text-red-500 hover:underline">Delete</button>
          </div>
        </div>
      </div>
    </template>

    <!-- EXPORTS -->
    <template v-if="activeTab === 'exports'">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <a v-for="exp in exportLinks" :key="exp.label" :href="apiBase + exp.path" target="_blank"
          class="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-sm transition-shadow block">
          <div class="text-2xl mb-2">{{ exp.icon }}</div>
          <p class="font-semibold text-slate-900 mb-1">{{ exp.label }}</p>
          <p class="text-xs text-slate-500">{{ exp.desc }}</p>
          <div class="mt-3 text-xs text-blue-600 font-medium">Download CSV →</div>
        </a>
      </div>
    </template>

    <!-- Modals -->
    <!-- Create Rule -->
    <Modal v-model="showCreateRule" title="Create Site Rule" size="md">
      <form class="space-y-4">
        <div>
          <label class="label">Name * (snake_case)</label>
          <input v-model="ruleForm.name" type="text" class="input font-mono" placeholder="max_exam_items" required />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Value *</label>
            <input v-model="ruleForm.value" type="text" class="input" required />
          </div>
          <div>
            <label class="label">Type</label>
            <select v-model="ruleForm.value_type" class="input">
              <option v-for="t in valueTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </div>
        <div>
          <label class="label">Description</label>
          <textarea v-model="ruleForm.description" class="input" rows="2" />
        </div>
        <div v-if="ruleError" class="text-sm text-red-600">{{ ruleError }}</div>
      </form>
      <template #footer>
        <button @click="showCreateRule = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreateRule" :disabled="savingRule" class="btn-primary">
          {{ savingRule ? 'Saving…' : 'Create Rule' }}
        </button>
      </template>
    </Modal>

    <!-- Edit Rule -->
    <Modal v-model="showEditRule" :title="`Edit: ${editRuleTarget?.name}`" size="md">
      <form class="space-y-4" v-if="editRuleTarget">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Value *</label>
            <input v-model="editRuleTarget.value" type="text" class="input" />
          </div>
          <div>
            <label class="label">Type</label>
            <select v-model="editRuleTarget.value_type" class="input">
              <option v-for="t in valueTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
        </div>
        <div>
          <label class="label">Description</label>
          <textarea v-model="editRuleTarget.description" class="input" rows="2" />
        </div>
      </form>
      <template #footer>
        <button @click="showEditRule = false" class="btn-secondary">Cancel</button>
        <button @click="handleUpdateRule" :disabled="savingRule" class="btn-primary">Save</button>
      </template>
    </Modal>

    <!-- Edit Param -->
    <Modal v-model="showEditParam" :title="`Edit: ${editParamTarget?.key}`" size="sm">
      <div class="space-y-4" v-if="editParamTarget">
        <div>
          <label class="label">Value *</label>
          <input v-model="editParamTarget.value" type="text" class="input" />
        </div>
      </div>
      <template #footer>
        <button @click="showEditParam = false" class="btn-secondary">Cancel</button>
        <button @click="handleUpdateParam" class="btn-primary">Save</button>
      </template>
    </Modal>

    <!-- Create Task -->
    <Modal v-model="showCreateTask" title="Create Task" size="md">
      <form class="space-y-4">
        <div>
          <label class="label">Name *</label>
          <input v-model="taskForm.name" type="text" class="input" required />
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Type *</label>
            <input v-model="taskForm.task_type" type="text" class="input font-mono" placeholder="data_export" />
          </div>
          <div>
            <label class="label">Priority (1-10)</label>
            <input v-model.number="taskForm.priority" type="number" min="1" max="10" class="input" />
          </div>
        </div>
        <div>
          <label class="label">Payload (JSON)</label>
          <textarea v-model="taskForm.payloadStr" class="input font-mono text-xs" rows="3" placeholder='{"key":"value"}' />
        </div>
        <div v-if="taskError" class="text-sm text-red-600">{{ taskError }}</div>
      </form>
      <template #footer>
        <button @click="showCreateTask = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreateTask" :disabled="savingTask" class="btn-primary">
          {{ savingTask ? 'Creating…' : 'Create Task' }}
        </button>
      </template>
    </Modal>

    <!-- Create Proxy -->
    <Modal v-model="showCreateProxy" title="Add Proxy" size="md">
      <form class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Label *</label>
            <input v-model="proxyForm.label" type="text" class="input" required />
          </div>
          <div>
            <label class="label">Protocol</label>
            <select v-model="proxyForm.protocol" class="input">
              <option>http</option><option>https</option><option>socks5</option>
            </select>
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Host *</label>
            <input v-model="proxyForm.host" type="text" class="input" placeholder="192.168.1.100" required />
          </div>
          <div>
            <label class="label">Port *</label>
            <input v-model.number="proxyForm.port" type="number" min="1" max="65535" class="input" required />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Username</label>
            <input v-model="proxyForm.username" type="text" class="input" />
          </div>
          <div>
            <label class="label">Password</label>
            <input v-model="proxyForm.password" type="password" class="input" />
          </div>
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Weight (1-10)</label>
            <input v-model.number="proxyForm.weight" type="number" min="1" max="10" class="input" />
          </div>
          <div>
            <label class="label">Region</label>
            <input v-model="proxyForm.region" type="text" class="input" placeholder="us-east" />
          </div>
        </div>
        <div v-if="proxyError" class="text-sm text-red-600">{{ proxyError }}</div>
      </form>
      <template #footer>
        <button @click="showCreateProxy = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreateProxy" :disabled="savingProxy" class="btn-primary">
          {{ savingProxy ? 'Adding…' : 'Add Proxy' }}
        </button>
      </template>
    </Modal>

    <!-- Create API Key -->
    <Modal v-model="showCreateKey" title="Issue API Key" size="md">
      <form class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Label *</label>
            <input v-model="keyForm.label" type="text" class="input" required />
          </div>
          <div>
            <label class="label">System Name *</label>
            <input v-model="keyForm.system_name" type="text" class="input" placeholder="erp-system" required />
          </div>
        </div>
        <div>
          <label class="label">Rate Limit (req/min)</label>
          <input v-model.number="keyForm.rate_limit_per_minute" type="number" min="1" max="6000" class="input" />
        </div>
        <div>
          <label class="label">Allowed IPs (comma-separated, blank = all)</label>
          <input v-model="keyForm.allowed_ips" type="text" class="input" placeholder="192.168.0.0/24,10.0.0.5" />
        </div>
        <div v-if="keyError" class="text-sm text-red-600">{{ keyError }}</div>
      </form>
      <template #footer>
        <button @click="showCreateKey = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreateKey" :disabled="savingKey" class="btn-primary">Issue Key</button>
      </template>
    </Modal>

    <!-- New Key Display Modal -->
    <Modal v-model="showNewKey" title="⚠ Save this key now" size="md">
      <div class="space-y-3">
        <p class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
          This key will <strong>not be shown again</strong>. Copy it now and store it securely.
        </p>
        <div class="bg-slate-900 text-green-400 rounded-lg p-4 font-mono text-sm break-all select-all">
          {{ newRawKey }}
        </div>
        <button @click="copyKey" class="btn-secondary w-full text-sm">Copy to Clipboard</button>
      </div>
      <template #footer>
        <button @click="showNewKey = false" class="btn-primary">I've saved it</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api/index.js'
import Modal from '../components/Modal.vue'

const apiBase = '/api'
const activeTab = ref('rules')
const tabs = [
  { key: 'rules', label: 'Site Rules' },
  { key: 'params', label: 'Parameters' },
  { key: 'tasks', label: 'Tasks' },
  { key: 'proxy', label: 'Proxy Pool' },
  { key: 'apikeys', label: 'API Keys' },
  { key: 'exports', label: 'Exports' },
]
const valueTypes = ['string', 'integer', 'boolean', 'decimal', 'json']

const exportLinks = [
  { label: 'Site Rules', path: '/admin/export/site-rules', icon: '📋', desc: 'All configured site rules' },
  { label: 'Admin Tasks', path: '/admin/export/tasks', icon: '⚙️', desc: 'Task history and status' },
  { label: 'Users', path: '/admin/export/users', icon: '👥', desc: 'User accounts and roles' },
  { label: 'API Keys', path: '/admin/export/api-keys', icon: '🔑', desc: 'Key metadata (no secrets)' },
  { label: 'CMS Pages', path: '/cms/pages/export', icon: '📄', desc: 'All CMS page records' },
]

// System status
const systemStatus = ref(null)
const statCards = computed(() => !systemStatus.value ? [] : [
  { label: 'Pending Tasks',  value: systemStatus.value.active_tasks_pending },
  { label: 'Running Tasks',  value: systemStatus.value.active_tasks_running },
  { label: 'Active API Keys',value: systemStatus.value.active_api_keys },
  { label: 'Active Proxies', value: systemStatus.value.active_proxies },
  { label: 'Site Rules',     value: systemStatus.value.site_rules_count },
  { label: 'System Params',  value: systemStatus.value.system_parameters_count },
])

// Rules state
const rules = ref([]); const rulesLoading = ref(false)
const showCreateRule = ref(false); const showEditRule = ref(false)
const savingRule = ref(false); const ruleError = ref('')
const editRuleTarget = ref(null)
const ruleForm = ref({ name: '', value: '', value_type: 'string', description: '' })

// Params state
const params = ref([]); const paramsLoading = ref(false)
const showEditParam = ref(false); const editParamTarget = ref(null)

// Tasks state
const tasks = ref([]); const tasksLoading = ref(false)
const showCreateTask = ref(false); const savingTask = ref(false); const taskError = ref('')
const taskStatusFilter = ref('')
const taskForm = ref({ name: '', task_type: '', priority: 5, payloadStr: '' })

// Proxy state
const proxies = ref([]); const proxiesLoading = ref(false)
const showCreateProxy = ref(false); const savingProxy = ref(false); const proxyError = ref('')
const proxyForm = ref({ label: '', host: '', port: 3128, protocol: 'http', username: '', password: '', weight: 5, region: '' })

// API key state
const apiKeys = ref([]); const keysLoading = ref(false)
const showCreateKey = ref(false); const savingKey = ref(false); const keyError = ref('')
const showNewKey = ref(false); const newRawKey = ref('')
const keyForm = ref({ label: '', system_name: '', rate_limit_per_minute: 60, allowed_ips: '' })

function formatDate(d) { return d ? new Date(d).toLocaleDateString() : '—' }
function isExpired(d) { return d && new Date(d) < new Date() }

function taskStatusColor(s) {
  return { pending: 'bg-yellow-100 text-yellow-700', running: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700', failed: 'bg-red-100 text-red-600',
    cancelled: 'bg-slate-100 text-slate-500' }[s] ?? 'bg-slate-100 text-slate-500'
}

async function fetchStatus() { try { const r = await api.get('/admin/system/status'); systemStatus.value = r.data } catch {} }
async function fetchRules() { rulesLoading.value = true; try { const r = await api.get('/admin/rules', { params: { limit: 200 } }); rules.value = r.data } finally { rulesLoading.value = false } }
async function fetchParams() { paramsLoading.value = true; try { const r = await api.get('/admin/parameters'); params.value = r.data } finally { paramsLoading.value = false } }
async function fetchTasks() { tasksLoading.value = true; try { const p = taskStatusFilter.value ? { status: taskStatusFilter.value } : {}; const r = await api.get('/admin/tasks', { params: p }); tasks.value = r.data } finally { tasksLoading.value = false } }
async function fetchProxies() { proxiesLoading.value = true; try { const r = await api.get('/admin/proxy-pool'); proxies.value = r.data } finally { proxiesLoading.value = false } }
async function fetchKeys() { keysLoading.value = true; try { const r = await api.get('/admin/api-keys'); apiKeys.value = r.data } finally { keysLoading.value = false } }

function openCreateRule() { ruleForm.value = { name: '', value: '', value_type: 'string', description: '' }; ruleError.value = ''; showCreateRule.value = true }
async function handleCreateRule() { ruleError.value = ''; savingRule.value = true; try { await api.post('/admin/rules', ruleForm.value); showCreateRule.value = false; await fetchRules() } catch (e) { ruleError.value = e.response?.data?.detail || 'Failed' } finally { savingRule.value = false } }
function editRule(r) { editRuleTarget.value = { ...r }; showEditRule.value = true }
async function handleUpdateRule() { savingRule.value = true; try { await api.put(`/admin/rules/${editRuleTarget.value.id}`, { value: editRuleTarget.value.value, value_type: editRuleTarget.value.value_type, description: editRuleTarget.value.description }); showEditRule.value = false; await fetchRules() } finally { savingRule.value = false } }
async function toggleRule(r) { await api.patch(`/admin/rules/${r.id}/toggle`); r.is_active = !r.is_active }
async function deleteRule(r) { if (!confirm('Delete rule?')) return; await api.delete(`/admin/rules/${r.id}`); rules.value = rules.value.filter(x => x.id !== r.id) }
function editParam(p) { editParamTarget.value = { ...p }; showEditParam.value = true }
async function handleUpdateParam() { await api.put(`/admin/parameters/${editParamTarget.value.key}`, { value: editParamTarget.value.value }); showEditParam.value = false; await fetchParams() }
function openCreateTask() { taskForm.value = { name: '', task_type: '', priority: 5, payloadStr: '' }; taskError.value = ''; showCreateTask.value = true }
async function handleCreateTask() { taskError.value = ''; savingTask.value = true; try { let payload = null; if (taskForm.value.payloadStr.trim()) { try { payload = JSON.parse(taskForm.value.payloadStr) } catch { taskError.value = 'Invalid JSON payload'; return } } await api.post('/admin/tasks', { name: taskForm.value.name, task_type: taskForm.value.task_type, priority: taskForm.value.priority, payload }); showCreateTask.value = false; await fetchTasks() } catch (e) { taskError.value = e.response?.data?.detail || 'Failed' } finally { savingTask.value = false } }
async function updateTaskStatus(task, s) { await api.patch(`/admin/tasks/${task.id}/status`, { status: s }); task.status = s }
async function cancelTask(t) { if (!confirm('Cancel task?')) return; await api.delete(`/admin/tasks/${t.id}`); t.status = 'cancelled' }
function openCreateProxy() { proxyForm.value = { label: '', host: '', port: 3128, protocol: 'http', username: '', password: '', weight: 5, region: '' }; proxyError.value = ''; showCreateProxy.value = true }
async function handleCreateProxy() { proxyError.value = ''; savingProxy.value = true; try { await api.post('/admin/proxy-pool', proxyForm.value); showCreateProxy.value = false; await fetchProxies() } catch (e) { proxyError.value = e.response?.data?.detail || 'Failed' } finally { savingProxy.value = false } }
async function deleteProxy(p) { if (!confirm('Remove proxy?')) return; await api.delete(`/admin/proxy-pool/${p.id}`); proxies.value = proxies.value.filter(x => x.id !== p.id) }
async function checkHealth(proxy) { const r = await api.patch(`/admin/proxy-pool/${proxy.id}/health-check`); proxy.is_healthy = r.data.is_healthy; proxy.last_checked_at = r.data.checked_at; alert(`${proxy.host}: ${r.data.detail}`) }
function openCreateKey() { keyForm.value = { label: '', system_name: '', rate_limit_per_minute: 60, allowed_ips: '' }; keyError.value = ''; showCreateKey.value = true }
async function handleCreateKey() { keyError.value = ''; savingKey.value = true; try { const r = await api.post('/admin/api-keys', keyForm.value); newRawKey.value = r.data.raw_key; showCreateKey.value = false; showNewKey.value = true; await fetchKeys() } catch (e) { keyError.value = e.response?.data?.detail || 'Failed' } finally { savingKey.value = false } }
async function rotateKey(k) { if (!confirm(`Rotate key for "${k.system_name}"? Old secret is immediately invalidated.`)) return; const r = await api.patch(`/admin/api-keys/${k.id}/rotate`); newRawKey.value = r.data.raw_key; showNewKey.value = true; await fetchKeys() }
async function toggleKey(k) { await api.patch(`/admin/api-keys/${k.id}/toggle`); k.is_active = !k.is_active }
async function deleteKey(k) { if (!confirm('Delete this API key? External systems using it will lose access.')) return; await api.delete(`/admin/api-keys/${k.id}`); apiKeys.value = apiKeys.value.filter(x => x.id !== k.id) }
async function copyKey() { await navigator.clipboard.writeText(newRawKey.value); alert('Copied!') }

onMounted(async () => {
  await fetchStatus()
  await Promise.all([fetchRules(), fetchParams(), fetchTasks(), fetchProxies(), fetchKeys()])
})
</script>
