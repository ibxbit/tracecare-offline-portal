<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">CMS Pages</h1>
        <p class="text-slate-500 text-sm mt-1">Manage content pages through the full editorial workflow</p>
      </div>
      <button @click="openCreate" class="btn-primary">+ New Page</button>
    </div>

    <!-- Status filter pills -->
    <div class="flex flex-wrap gap-2 mb-5">
      <button v-for="s in statusFilters" :key="s.value"
        :class="['text-xs px-3 py-1.5 rounded-full border transition-colors',
          activeStatusFilter === s.value
            ? 'bg-blue-600 border-blue-600 text-white'
            : 'border-slate-200 text-slate-600 hover:border-blue-300']"
        @click="activeStatusFilter = s.value; fetchPages()">
        {{ s.label }}
      </button>
    </div>

    <!-- Pages table -->
    <div v-if="loading" class="text-center py-16 text-slate-400">Loading…</div>
    <div v-else-if="!pages.length" class="text-center py-16 text-slate-400">No pages found.</div>
    <div v-else class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <table class="w-full text-sm">
        <thead class="bg-slate-50 border-b border-slate-200">
          <tr>
            <th class="text-left px-4 py-3 font-semibold text-slate-600">Title / Slug</th>
            <th class="text-left px-4 py-3 font-semibold text-slate-600">Status</th>
            <th class="text-left px-4 py-3 font-semibold text-slate-600">Store / Locale</th>
            <th class="text-left px-4 py-3 font-semibold text-slate-600">Rev</th>
            <th class="text-left px-4 py-3 font-semibold text-slate-600">Updated</th>
            <th class="text-right px-4 py-3 font-semibold text-slate-600">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-100">
          <tr v-for="page in pages" :key="page.id" class="hover:bg-slate-50">
            <td class="px-4 py-3">
              <div class="font-medium text-slate-900">{{ page.title }}</div>
              <div class="text-xs text-slate-400 font-mono">{{ page.slug }}</div>
            </td>
            <td class="px-4 py-3">
              <span :class="['text-xs font-medium px-2 py-0.5 rounded-full', statusClass(page.status)]">
                {{ page.status }}
              </span>
            </td>
            <td class="px-4 py-3 text-slate-500 text-xs">
              {{ page.store_id || 'default' }} / {{ page.locale || 'en' }}
            </td>
            <td class="px-4 py-3 text-slate-400 text-xs">r{{ page.current_revision }}</td>
            <td class="px-4 py-3 text-slate-400 text-xs">{{ fmtDate(page.updated_at) }}</td>
            <td class="px-4 py-3">
              <div class="flex justify-end gap-1.5 flex-wrap">
                <button @click="openEdit(page)" class="text-xs px-2 py-1 rounded border border-slate-200 text-slate-600 hover:bg-slate-50">
                  Edit
                </button>
                <!-- Workflow actions based on current status -->
                <button v-if="page.status === 'draft'"
                  @click="workflowAction(page, 'submit-review')"
                  class="text-xs px-2 py-1 rounded border border-blue-200 text-blue-600 hover:bg-blue-50">
                  Submit
                </button>
                <template v-if="page.status === 'review'">
                  <button @click="workflowAction(page, 'approve')"
                    class="text-xs px-2 py-1 rounded border border-green-200 text-green-700 hover:bg-green-50">
                    Approve
                  </button>
                  <button @click="openReject(page)"
                    class="text-xs px-2 py-1 rounded border border-orange-200 text-orange-600 hover:bg-orange-50">
                    Reject
                  </button>
                </template>
                <button v-if="page.status === 'published'"
                  @click="workflowAction(page, 'archive')"
                  class="text-xs px-2 py-1 rounded border border-slate-200 text-slate-500 hover:bg-slate-50">
                  Archive
                </button>
                <button v-if="page.status === 'archived'"
                  @click="workflowAction(page, 'restore')"
                  class="text-xs px-2 py-1 rounded border border-purple-200 text-purple-600 hover:bg-purple-50">
                  Restore
                </button>
                <button @click="openRevisions(page)"
                  class="text-xs px-2 py-1 rounded border border-slate-200 text-slate-500 hover:bg-slate-50">
                  History
                </button>
                <button @click="confirmDelete(page)"
                  class="text-xs px-2 py-1 rounded border border-red-200 text-red-500 hover:bg-red-50">
                  Delete
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- ── Create / Edit Modal ────────────────────────────────────────────── -->
    <Modal v-model="showEditor" :title="editingPage ? 'Edit Page' : 'New Page'" size="xl">
      <form @submit.prevent="handleSave" class="space-y-5">
        <!-- Core content -->
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Title *</label>
            <input v-model="form.title" type="text" class="input" required @input="autoSlug" />
          </div>
          <div>
            <label class="label">Slug *</label>
            <input v-model="form.slug" type="text" class="input" required placeholder="url-friendly-slug" />
          </div>
        </div>
        <div>
          <label class="label">Content</label>
          <textarea v-model="form.content" class="input font-mono text-sm" rows="8"
            placeholder="Page content (supports plain text or HTML)…" />
        </div>

        <!-- Store / locale / page type -->
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="label">Store</label>
            <input v-model="form.store_id" type="text" class="input" placeholder="default" />
          </div>
          <div>
            <label class="label">Locale</label>
            <input v-model="form.locale" type="text" class="input" placeholder="en" maxlength="10" />
          </div>
          <div>
            <label class="label">Page Type</label>
            <input v-model="form.page_type" type="text" class="input" placeholder="blog, policy, faq…" />
          </div>
        </div>

        <!-- SEO -->
        <details class="border border-slate-200 rounded-lg">
          <summary class="px-4 py-2.5 cursor-pointer text-sm font-medium text-slate-700 select-none">
            SEO Metadata
          </summary>
          <div class="px-4 pb-4 pt-2 space-y-3 border-t border-slate-100">
            <div>
              <label class="label">SEO Title</label>
              <input v-model="form.seo_title" type="text" class="input" maxlength="255" />
            </div>
            <div>
              <label class="label">SEO Description</label>
              <textarea v-model="form.seo_description" class="input" rows="2" maxlength="500" />
            </div>
            <div>
              <label class="label">SEO Keywords (comma-separated)</label>
              <input v-model="form.seo_keywords" type="text" class="input" />
            </div>
          </div>
        </details>

        <!-- Sitemap -->
        <details class="border border-slate-200 rounded-lg">
          <summary class="px-4 py-2.5 cursor-pointer text-sm font-medium text-slate-700 select-none">
            Sitemap Settings
          </summary>
          <div class="px-4 pb-4 pt-2 border-t border-slate-100">
            <label class="flex items-center gap-2 text-sm mb-3">
              <input v-model="form.is_in_sitemap" type="checkbox" class="rounded" />
              Include in sitemap
            </label>
            <div v-if="form.is_in_sitemap" class="grid grid-cols-2 gap-4">
              <div>
                <label class="label">Priority (0.0 – 1.0)</label>
                <input v-model.number="form.sitemap_priority" type="number"
                  step="0.1" min="0" max="1" class="input" />
              </div>
              <div>
                <label class="label">Change Frequency</label>
                <select v-model="form.sitemap_changefreq" class="input">
                  <option v-for="f in changefreqOptions" :key="f" :value="f">{{ f }}</option>
                </select>
              </div>
            </div>
          </div>
        </details>

        <!-- Change note (edit only) -->
        <div v-if="editingPage">
          <label class="label">Change Note (saved with revision)</label>
          <input v-model="form.change_note" type="text" class="input" placeholder="Briefly describe what you changed…" />
        </div>

        <div v-if="saveError" class="text-sm text-red-600 bg-red-50 rounded p-2">{{ saveError }}</div>
      </form>
      <template #footer>
        <button @click="showEditor = false" class="btn-secondary">Cancel</button>
        <button @click="handleSave" :disabled="saving" class="btn-primary">
          {{ saving ? 'Saving…' : (editingPage ? 'Update Page' : 'Create Page') }}
        </button>
      </template>
    </Modal>

    <!-- ── Reject Modal ───────────────────────────────────────────────────── -->
    <Modal v-model="showReject" title="Reject Page" size="sm">
      <div class="space-y-3">
        <p class="text-sm text-slate-600">
          Rejecting <strong>{{ rejectTarget?.title }}</strong> will return it to draft.
        </p>
        <div>
          <label class="label">Reason (optional)</label>
          <textarea v-model="rejectReason" class="input" rows="3" placeholder="Feedback for the author…" />
        </div>
      </div>
      <template #footer>
        <button @click="showReject = false" class="btn-secondary">Cancel</button>
        <button @click="handleReject" :disabled="workflowBusy" class="btn-primary">
          {{ workflowBusy ? 'Rejecting…' : 'Reject' }}
        </button>
      </template>
    </Modal>

    <!-- ── Revisions Modal ────────────────────────────────────────────────── -->
    <Modal v-model="showRevisions" :title="`Revision History — ${revisionsPage?.title}`" size="lg">
      <div v-if="revisionsLoading" class="py-8 text-center text-slate-400">Loading…</div>
      <div v-else-if="!revisions.length" class="py-8 text-center text-slate-400">No revisions yet.</div>
      <div v-else class="space-y-2 max-h-96 overflow-y-auto">
        <div v-for="rev in revisions" :key="rev.id"
          class="flex items-start justify-between p-3 rounded-lg border border-slate-200 hover:bg-slate-50">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <span class="font-mono text-xs font-semibold text-slate-700">r{{ rev.revision_number }}</span>
              <span :class="['text-xs px-1.5 py-0.5 rounded', statusClass(rev.status_snapshot)]">
                {{ rev.status_snapshot }}
              </span>
            </div>
            <div class="text-xs text-slate-600 truncate">{{ rev.title_snapshot }}</div>
            <div v-if="rev.change_note" class="text-xs text-slate-400 mt-0.5 italic">{{ rev.change_note }}</div>
            <div class="text-xs text-slate-300 mt-0.5">{{ fmtDate(rev.created_at) }}</div>
          </div>
          <button
            v-if="rev.revision_number !== revisionsPage?.current_revision"
            @click="rollback(revisionsPage, rev.revision_number)"
            :disabled="rollbackBusy === rev.revision_number"
            class="ml-3 text-xs px-2 py-1 rounded border border-amber-200 text-amber-700 hover:bg-amber-50 shrink-0">
            {{ rollbackBusy === rev.revision_number ? '…' : 'Rollback' }}
          </button>
          <span v-else class="ml-3 text-xs text-slate-400 italic shrink-0">current</span>
        </div>
      </div>
      <template #footer>
        <button @click="showRevisions = false" class="btn-secondary">Close</button>
      </template>
    </Modal>

    <!-- ── Delete Confirm ─────────────────────────────────────────────────── -->
    <Modal v-model="showDelete" title="Confirm Delete" size="sm">
      <p class="text-slate-600">Delete page <strong>{{ selectedPage?.title }}</strong>? This cannot be undone.</p>
      <template #footer>
        <button @click="showDelete = false" class="btn-secondary">Cancel</button>
        <button @click="handleDelete" :disabled="deleting" class="btn-danger">
          {{ deleting ? 'Deleting…' : 'Delete' }}
        </button>
      </template>
    </Modal>

    <!-- Global action feedback -->
    <div v-if="actionMsg"
      :class="['fixed bottom-4 right-4 z-50 px-4 py-2.5 rounded-lg shadow-lg text-sm font-medium transition-all',
        actionMsgType === 'error' ? 'bg-red-600 text-white' : 'bg-green-600 text-white']">
      {{ actionMsg }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api/index.js'
import Modal from '../components/Modal.vue'

// ── Data ──────────────────────────────────────────────────────────────────────
const pages = ref([])
const loading = ref(true)
const activeStatusFilter = ref('')

const statusFilters = [
  { value: '', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'review', label: 'In Review' },
  { value: 'published', label: 'Published' },
  { value: 'archived', label: 'Archived' },
]

const changefreqOptions = ['always', 'hourly', 'daily', 'weekly', 'monthly', 'yearly', 'never']

// ── Editor ────────────────────────────────────────────────────────────────────
const showEditor = ref(false)
const saving = ref(false)
const saveError = ref('')
const editingPage = ref(null)

const _blankForm = () => ({
  title: '', slug: '', content: '',
  store_id: 'default', locale: 'en', page_type: '',
  seo_title: '', seo_description: '', seo_keywords: '',
  is_in_sitemap: true, sitemap_priority: 0.5, sitemap_changefreq: 'monthly',
  change_note: '',
})
const form = ref(_blankForm())

// ── Workflow ──────────────────────────────────────────────────────────────────
const workflowBusy = ref(false)
const showReject = ref(false)
const rejectTarget = ref(null)
const rejectReason = ref('')

// ── Revisions ─────────────────────────────────────────────────────────────────
const showRevisions = ref(false)
const revisionsPage = ref(null)
const revisions = ref([])
const revisionsLoading = ref(false)
const rollbackBusy = ref(null)

// ── Delete ────────────────────────────────────────────────────────────────────
const showDelete = ref(false)
const deleting = ref(false)
const selectedPage = ref(null)

// ── Feedback toast ────────────────────────────────────────────────────────────
const actionMsg = ref('')
const actionMsgType = ref('success')
let _toastTimer = null

function showToast(msg, type = 'success') {
  actionMsg.value = msg
  actionMsgType.value = type
  clearTimeout(_toastTimer)
  _toastTimer = setTimeout(() => { actionMsg.value = '' }, 3500)
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtDate(d) {
  return d ? new Date(d).toLocaleString() : '—'
}

function statusClass(status) {
  return {
    draft:     'bg-slate-100 text-slate-600',
    review:    'bg-blue-100 text-blue-700',
    published: 'bg-green-100 text-green-700',
    archived:  'bg-amber-100 text-amber-700',
  }[status] ?? 'bg-slate-100 text-slate-500'
}

function autoSlug() {
  if (!editingPage.value) {
    // Order matters: whitespace → hyphen first, THEN strip remaining
    // non-alphanumeric/non-hyphen characters. For a title like
    // 'FAQ & Policies!' this produces 'faq--policies' rather than
    // the 'faq---policies-' you'd get from replacing punctuation with
    // extra hyphens.
    form.value.slug = form.value.title
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .slice(0, 100)
  }
}

// ── Fetch ─────────────────────────────────────────────────────────────────────
async function fetchPages() {
  loading.value = true
  try {
    const params = { limit: 200 }
    if (activeStatusFilter.value) params.status = activeStatusFilter.value
    const res = await api.get('/cms/pages', { params })
    pages.value = res.data
  } finally {
    loading.value = false
  }
}

// ── Create / Edit ─────────────────────────────────────────────────────────────
function openCreate() {
  editingPage.value = null
  form.value = _blankForm()
  saveError.value = ''
  showEditor.value = true
}

function openEdit(page) {
  editingPage.value = page
  form.value = {
    title: page.title,
    slug: page.slug,
    content: page.content ?? '',
    store_id: page.store_id ?? 'default',
    locale: page.locale ?? 'en',
    page_type: page.page_type ?? '',
    seo_title: page.seo_title ?? '',
    seo_description: page.seo_description ?? '',
    seo_keywords: page.seo_keywords ?? '',
    is_in_sitemap: page.is_in_sitemap ?? true,
    sitemap_priority: page.sitemap_priority ?? 0.5,
    sitemap_changefreq: page.sitemap_changefreq ?? 'monthly',
    change_note: '',
  }
  saveError.value = ''
  showEditor.value = true
}

async function handleSave() {
  saveError.value = ''
  saving.value = true
  try {
    const payload = {
      title: form.value.title,
      slug: form.value.slug,
      content: form.value.content,
      store_id: form.value.store_id || 'default',
      locale: form.value.locale || 'en',
      page_type: form.value.page_type || null,
      seo_title: form.value.seo_title || null,
      seo_description: form.value.seo_description || null,
      seo_keywords: form.value.seo_keywords || null,
      is_in_sitemap: form.value.is_in_sitemap,
      sitemap_priority: form.value.sitemap_priority,
      sitemap_changefreq: form.value.sitemap_changefreq,
    }
    if (editingPage.value) {
      if (form.value.change_note) payload.change_note = form.value.change_note
      await api.put(`/cms/pages/${editingPage.value.id}`, payload)
      showToast('Page updated.')
    } else {
      await api.post('/cms/pages', payload)
      showToast('Page created.')
    }
    showEditor.value = false
    await fetchPages()
  } catch (err) {
    saveError.value = err.response?.data?.detail || 'Failed to save page.'
  } finally {
    saving.value = false
  }
}

// ── Workflow actions ──────────────────────────────────────────────────────────
async function workflowAction(page, action) {
  workflowBusy.value = true
  try {
    // Backend WorkflowTransitionRequest requires a JSON body with optional `note`.
    // Omitting the body entirely causes FastAPI to return 422.
    await api.post(`/cms/pages/${page.id}/${action}`, { note: null })
    const labels = {
      'submit-review': 'Submitted for review.',
      approve: 'Page approved and published.',
      archive: 'Page archived.',
      restore: 'Page restored to draft.',
    }
    showToast(labels[action] ?? 'Done.')
    await fetchPages()
  } catch (err) {
    showToast(err.response?.data?.detail || `Action "${action}" failed.`, 'error')
  } finally {
    workflowBusy.value = false
  }
}

function openReject(page) {
  rejectTarget.value = page
  rejectReason.value = ''
  showReject.value = true
}

async function handleReject() {
  workflowBusy.value = true
  try {
    // Backend WorkflowTransitionRequest uses `note`, not `reason`.
    await api.post(`/cms/pages/${rejectTarget.value.id}/reject`, {
      note: rejectReason.value || null,
    })
    showReject.value = false
    showToast('Page rejected — returned to draft.')
    await fetchPages()
  } catch (err) {
    showToast(err.response?.data?.detail || 'Reject failed.', 'error')
  } finally {
    workflowBusy.value = false
  }
}

// ── Revisions ─────────────────────────────────────────────────────────────────
async function openRevisions(page) {
  revisionsPage.value = page
  revisions.value = []
  revisionsLoading.value = true
  showRevisions.value = true
  try {
    const res = await api.get(`/cms/pages/${page.id}/revisions`)
    revisions.value = (res.data || []).slice().reverse() // newest first
  } finally {
    revisionsLoading.value = false
  }
}

async function rollback(page, revisionNumber) {
  if (!confirm(`Roll back "${page.title}" to revision r${revisionNumber}? Current content will be overwritten.`)) return
  rollbackBusy.value = revisionNumber
  try {
    // Backend rollback endpoint also expects WorkflowTransitionRequest body.
    await api.post(`/cms/pages/${page.id}/rollback/${revisionNumber}`, { note: null })
    showToast(`Rolled back to r${revisionNumber}.`)
    showRevisions.value = false
    await fetchPages()
  } catch (err) {
    showToast(err.response?.data?.detail || 'Rollback failed.', 'error')
  } finally {
    rollbackBusy.value = null
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────
function confirmDelete(page) {
  selectedPage.value = page
  showDelete.value = true
}

async function handleDelete() {
  deleting.value = true
  try {
    await api.delete(`/cms/pages/${selectedPage.value.id}`)
    showDelete.value = false
    showToast('Page deleted.')
    await fetchPages()
  } catch (err) {
    showToast(err.response?.data?.detail || 'Delete failed.', 'error')
  } finally {
    deleting.value = false
  }
}

onMounted(fetchPages)
</script>
