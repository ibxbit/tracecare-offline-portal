<template>
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-2xl font-bold text-slate-900">Reviews</h1>
        <p class="text-slate-500 text-sm mt-1">Product and service reviews with credibility scoring</p>
      </div>
      <button @click="openCreate" class="btn-primary">+ Write Review</button>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap gap-3 mb-6">
      <input v-model="filters.search" @input="debouncedFetch" type="text"
        class="input max-w-xs" placeholder="Search reviews..." />
      <select v-model="filters.subject_type" @change="fetchReviews" class="input w-40">
        <option value="">All types</option>
        <option value="product">Product</option>
        <option value="exam_type">Exam Type</option>
        <option value="catalog_item">Catalog Item</option>
      </select>
      <select v-model="filters.min_rating" @change="fetchReviews" class="input w-32">
        <option value="">All ratings</option>
        <option v-for="n in [5,4,3,2,1]" :key="n" :value="n">{{ n }}+ ★</option>
      </select>
      <label class="flex items-center gap-2 text-sm text-slate-600">
        <input v-model="filters.verified_only" @change="fetchReviews" type="checkbox" class="rounded" />
        Verified only
      </label>
      <!-- Moderation sort (admin/catalog) -->
      <select v-if="authStore.isRole('admin','catalog_manager')" v-model="filters.sort_by" @change="fetchReviews" class="input w-44">
        <option value="created_at">Newest first</option>
        <option value="rating">By rating</option>
        <option value="credibility_score">By credibility</option>
        <option value="pinned_first">Pinned first</option>
      </select>
    </div>

    <!-- Summary bar -->
    <div v-if="summary" class="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6 flex flex-wrap gap-6">
      <div class="text-center">
        <div class="text-2xl font-bold text-blue-700">{{ summary.avg_rating?.toFixed(1) ?? '—' }}</div>
        <div class="text-xs text-slate-500">Avg Rating</div>
      </div>
      <div class="text-center">
        <div class="text-2xl font-bold text-blue-700">{{ summary.total_count ?? 0 }}</div>
        <div class="text-xs text-slate-500">Total Reviews</div>
      </div>
      <div class="text-center">
        <div class="text-2xl font-bold text-blue-700">{{ summary.verified_review_count ?? 0 }}</div>
        <div class="text-xs text-slate-500">Verified</div>
      </div>
      <div v-if="summary.rating_distribution" class="flex gap-1 items-end">
        <div v-for="n in [5,4,3,2,1]" :key="n" class="flex flex-col items-center gap-0.5">
          <div class="text-xs text-slate-400">{{ summary.rating_distribution[n] ?? 0 }}</div>
          <div class="w-6 bg-amber-400 rounded-sm"
            :style="`height: ${Math.max(4, ((summary.rating_distribution[n] ?? 0) / Math.max(1, summary.total_count)) * 40)}px`" />
          <div class="text-xs text-slate-400">{{ n }}★</div>
        </div>
      </div>
    </div>

    <div v-if="loading" class="text-center py-16 text-slate-400">Loading…</div>
    <div v-else-if="!reviews.length" class="text-center py-16 text-slate-400">No reviews found.</div>

    <div v-else class="space-y-4">
      <div v-for="review in reviews" :key="review.id"
        :class="['bg-white rounded-xl border shadow-sm p-5 transition-all',
          review.is_pinned ? 'border-amber-300 ring-1 ring-amber-200' :
          review.is_collapsed ? 'border-slate-200 opacity-60' : 'border-slate-200']">

        <!-- Pinned badge -->
        <div v-if="review.is_pinned" class="flex items-center gap-1.5 text-amber-600 text-xs font-semibold mb-2">
          <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
            <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
          </svg>
          Pinned Review
        </div>

        <div class="flex items-start justify-between gap-4">
          <div class="flex-1">
            <!-- Stars + type + follow-up tag -->
            <div class="flex items-center gap-3 mb-2 flex-wrap">
              <div class="flex gap-0.5">
                <svg v-for="n in 5" :key="n"
                  :class="['w-4 h-4', n <= review.rating ? 'text-amber-400' : 'text-slate-200']"
                  fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                </svg>
              </div>
              <span class="text-xs bg-slate-100 text-slate-600 rounded-full px-2 py-0.5 capitalize">{{ review.subject_type?.replace('_', ' ') }}</span>
              <span v-if="review.is_followup" class="text-xs bg-purple-100 text-purple-700 rounded-full px-2 py-0.5">Follow-up</span>
              <span v-if="review.order_id" class="text-xs bg-green-100 text-green-700 rounded-full px-2 py-0.5">Verified Purchase</span>
              <span v-if="review.is_collapsed" class="text-xs bg-slate-200 text-slate-500 rounded-full px-2 py-0.5">Collapsed</span>
            </div>

            <!-- Body (collapsed = truncated) -->
            <p v-if="!review.is_collapsed" class="text-sm text-slate-700 mb-3">{{ review.comment }}</p>
            <p v-else class="text-xs text-slate-400 italic mb-3">This review has been collapsed by a moderator.
              <button @click="review._expand = !review._expand" class="text-blue-500 underline ml-1">
                {{ review._expand ? 'Hide' : 'Show' }}
              </button>
            </p>
            <p v-if="review.is_collapsed && review._expand" class="text-sm text-slate-500 mb-3">{{ review.comment }}</p>

            <!-- Tags -->
            <div v-if="review.tags?.length" class="flex flex-wrap gap-1.5 mb-3">
              <span v-for="tag in review.tags" :key="tag"
                class="text-xs bg-blue-50 text-blue-600 rounded-full px-2 py-0.5">{{ tag }}</span>
            </div>

            <!-- Images -->
            <div v-if="review.image_count > 0" class="flex gap-2 mb-3">
              <div v-for="n in Math.min(review.image_count, 6)" :key="n"
                class="w-16 h-16 bg-slate-100 rounded-lg flex items-center justify-center text-slate-400 text-xs">
                Img {{ n }}
              </div>
            </div>

            <!-- Credibility (staff/admin) -->
            <div v-if="authStore.isRole('admin','catalog_manager','clinic_staff') && review.credibility_score !== undefined"
              class="text-xs text-slate-400">
              Credibility: <span class="font-semibold text-slate-600">{{ (review.credibility_score * 100).toFixed(0) }}%</span>
            </div>

            <!-- Moderation note -->
            <div v-if="review.moderation_note && authStore.isRole('admin','catalog_manager')"
              class="mt-2 text-xs text-orange-700 bg-orange-50 rounded px-2 py-1">
              Mod note: {{ review.moderation_note }}
            </div>
          </div>

          <div class="text-right shrink-0">
            <div class="text-xs text-slate-400">{{ formatDate(review.created_at) }}</div>
            <div class="text-xs text-slate-400 mt-1">By #{{ review.reviewer_id }}</div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex items-center justify-between pt-3 mt-3 border-t border-slate-100">
          <!-- Follow-up (end user, within 14 days) -->
          <button v-if="canFollowUp(review)" @click="openFollowup(review)"
            class="text-xs text-purple-600 hover:text-purple-800 font-medium">
            + Write Follow-up
          </button>
          <span v-else />

          <!-- Moderation actions -->
          <div v-if="authStore.isRole('admin','catalog_manager')" class="flex gap-2">
            <button @click="togglePin(review)"
              :class="['text-xs px-2 py-1 rounded border transition-colors',
                review.is_pinned ? 'bg-amber-50 border-amber-300 text-amber-700' : 'border-slate-200 text-slate-500 hover:border-amber-300']">
              {{ review.is_pinned ? 'Unpin' : 'Pin' }}
            </button>
            <button @click="toggleCollapse(review)"
              :class="['text-xs px-2 py-1 rounded border transition-colors',
                review.is_collapsed ? 'bg-slate-50 border-slate-300 text-slate-600' : 'border-slate-200 text-slate-500 hover:border-red-300']">
              {{ review.is_collapsed ? 'Expand' : 'Collapse' }}
            </button>
            <button @click="deleteReview(review)" class="text-xs px-2 py-1 rounded border border-red-200 text-red-500 hover:bg-red-50">
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="total > filters.limit" class="flex justify-center gap-2 mt-8">
      <button @click="prevPage" :disabled="filters.skip === 0" class="btn-secondary text-sm">← Prev</button>
      <span class="self-center text-sm text-slate-500">
        {{ filters.skip + 1 }}–{{ Math.min(filters.skip + filters.limit, total) }} of {{ total }}
      </span>
      <button @click="nextPage" :disabled="filters.skip + filters.limit >= total" class="btn-secondary text-sm">Next →</button>
    </div>

    <!-- Create Review Modal -->
    <Modal v-model="showCreate" title="Write a Review" size="lg">
      <form @submit.prevent="handleCreate" class="space-y-4">
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="label">Subject Type *</label>
            <select v-model="createForm.subject_type" @change="createForm.subject_id = null; createForm.subject_text = ''"
              class="input" required>
              <option value="">Select…</option>
              <option value="product">Product</option>
              <option value="exam_type">Exam Type</option>
              <option value="catalog_item">Catalog Item</option>
            </select>
          </div>
          <!-- exam_type uses a text label (subject_text); other types use a numeric ID (subject_id) -->
          <div v-if="createForm.subject_type === 'exam_type'">
            <label class="label">Exam Type Name *</label>
            <input v-model="createForm.subject_text" type="text" class="input" required
              placeholder="e.g. CBC, Urinalysis, X-Ray" />
          </div>
          <div v-else>
            <label class="label">Subject ID *</label>
            <input v-model.number="createForm.subject_id" type="number" class="input"
              :required="!!createForm.subject_type" placeholder="Item ID" />
          </div>
        </div>
        <div>
          <label class="label">Order ID (optional — verifies purchase)</label>
          <input v-model.number="createForm.order_id" type="number" class="input" placeholder="Leave blank if no order" />
        </div>
        <div>
          <label class="label">Rating *</label>
          <div class="flex gap-1">
            <button v-for="n in 5" :key="n" type="button" @click="createForm.rating = n">
              <svg :class="['w-8 h-8', n <= createForm.rating ? 'text-amber-400' : 'text-slate-200']"
                fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            </button>
          </div>
        </div>
        <div>
          <label class="label">Comment * (max 1000 chars)</label>
          <textarea v-model="createForm.comment" class="input" rows="4" maxlength="1000" required />
          <p class="text-xs text-slate-400 text-right mt-1">{{ createForm.comment.length }}/1000</p>
        </div>
        <div>
          <label class="label">Tags (comma-separated)</label>
          <input v-model="tagsInput" type="text" class="input" placeholder="quality, fast-delivery, organic" />
        </div>
        <div>
          <label class="label">Images (max 6, JPG/PNG only)</label>
          <input ref="imageInput" type="file" accept="image/jpeg,image/png" multiple
            @change="handleImageSelect" class="block w-full text-sm text-slate-500
              file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0
              file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700" />
          <div v-if="selectedImages.length" class="flex gap-2 mt-2 flex-wrap">
            <div v-for="(img, i) in selectedImages" :key="i"
              class="relative w-16 h-16 rounded-lg overflow-hidden border border-slate-200">
              <img :src="img.preview" class="w-full h-full object-cover" />
              <button @click="removeImage(i)"
                class="absolute top-0.5 right-0.5 bg-red-500 text-white rounded-full w-4 h-4 text-xs flex items-center justify-center">×</button>
            </div>
          </div>
        </div>
        <!-- Cooldown warning (client-side anti-spam) -->
        <div v-if="cooldownSeconds > 0" class="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-2 flex items-center gap-2">
          <svg class="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2"
              d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          Please wait <strong class="mx-1">{{ fmtCooldown(cooldownSeconds) }}</strong> before submitting another review for this order.
        </div>
        <div v-if="createError" class="text-sm text-red-600 bg-red-50 rounded p-2">{{ createError }}</div>
      </form>
      <template #footer>
        <button @click="showCreate = false" class="btn-secondary">Cancel</button>
        <button @click="handleCreate" :disabled="creating || cooldownSeconds > 0" class="btn-primary"
          :title="cooldownSeconds > 0 ? `Wait ${fmtCooldown(cooldownSeconds)}` : ''">
          {{ creating ? 'Submitting…' : cooldownSeconds > 0 ? `Wait ${fmtCooldown(cooldownSeconds)}` : 'Submit Review' }}
        </button>
      </template>
    </Modal>

    <!-- Follow-up Modal -->
    <Modal v-model="showFollowup" title="Write Follow-up" size="md">
      <div class="space-y-4">
        <p class="text-sm text-slate-500">Adding a follow-up to your review from {{ formatDate(followupTarget?.created_at) }}</p>
        <div>
          <label class="label">Rating *</label>
          <div class="flex gap-1">
            <button v-for="n in 5" :key="n" type="button" @click="followupForm.rating = n">
              <svg :class="['w-7 h-7', n <= followupForm.rating ? 'text-amber-400' : 'text-slate-200']"
                fill="currentColor" viewBox="0 0 20 20">
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            </button>
          </div>
        </div>
        <div>
          <label class="label">Comment *</label>
          <textarea v-model="followupForm.comment" class="input" rows="3" maxlength="1000" required />
        </div>
        <div v-if="followupError" class="text-sm text-red-600">{{ followupError }}</div>
      </div>
      <template #footer>
        <button @click="showFollowup = false" class="btn-secondary">Cancel</button>
        <button @click="handleFollowup" :disabled="submittingFollowup" class="btn-primary">
          {{ submittingFollowup ? 'Submitting…' : 'Submit Follow-up' }}
        </button>
      </template>
    </Modal>

    <!-- Collapse note modal -->
    <Modal v-model="showCollapseNote" title="Collapse Review" size="sm">
      <div class="space-y-3">
        <p class="text-sm text-slate-600">Add a moderation note (optional):</p>
        <textarea v-model="moderationNote" class="input" rows="3" placeholder="Reason for collapsing..." />
      </div>
      <template #footer>
        <button @click="showCollapseNote = false" class="btn-secondary">Cancel</button>
        <button @click="confirmCollapse" class="btn-primary">Collapse</button>
      </template>
    </Modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, watch } from 'vue'
import api from '../api/index.js'
import Modal from '../components/Modal.vue'
import { useAuthStore } from '../stores/auth.js'

const authStore = useAuthStore()

// ── Per-order cooldown (10 min anti-spam, client-side) ────────────────────────
const COOLDOWN_MS = 10 * 60 * 1000
const COOLDOWN_STORAGE_KEY = 'tc_review_cooldowns'

function _loadCooldowns() {
  try { return JSON.parse(localStorage.getItem(COOLDOWN_STORAGE_KEY) || '{}') } catch { return {} }
}
function _saveCooldowns(cd) {
  localStorage.setItem(COOLDOWN_STORAGE_KEY, JSON.stringify(cd))
}
function _cooldownExpiryFor(orderId) {
  if (!orderId) return 0
  const cd = _loadCooldowns()
  return cd[String(orderId)] || 0
}
function _recordCooldown(orderId) {
  if (!orderId) return
  const cd = _loadCooldowns()
  cd[String(orderId)] = Date.now() + COOLDOWN_MS
  _saveCooldowns(cd)
}

const cooldownSeconds = ref(0)
let _cooldownTimer = null

function _startCooldownTick(orderId) {
  clearInterval(_cooldownTimer)
  _cooldownTimer = setInterval(() => {
    const expiry = _cooldownExpiryFor(orderId)
    const remaining = Math.max(0, Math.ceil((expiry - Date.now()) / 1000))
    cooldownSeconds.value = remaining
    if (remaining === 0) clearInterval(_cooldownTimer)
  }, 1000)
}

function _checkCooldown(orderId) {
  const expiry = _cooldownExpiryFor(orderId)
  const remaining = Math.max(0, Math.ceil((expiry - Date.now()) / 1000))
  cooldownSeconds.value = remaining
  if (remaining > 0) _startCooldownTick(orderId)
}

function fmtCooldown(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

const reviews = ref([])
const summary = ref(null)
const loading = ref(true)
const total = ref(0)
const filters = reactive({
  search: '', subject_type: '', min_rating: '', verified_only: false,
  sort_by: 'created_at', skip: 0, limit: 20,
})

// Create form
const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const createForm = ref({ subject_type: '', subject_id: null, subject_text: '', order_id: null, rating: 0, comment: '' })
const tagsInput = ref('')
const selectedImages = ref([])
const imageInput = ref(null)

// Follow-up form
const showFollowup = ref(false)
const followupTarget = ref(null)
const submittingFollowup = ref(false)
const followupError = ref('')
const followupForm = ref({ rating: 0, comment: '' })

// Collapse
const showCollapseNote = ref(false)
const collapseTarget = ref(null)
const moderationNote = ref('')

let debounceTimer = null
function debouncedFetch() { clearTimeout(debounceTimer); debounceTimer = setTimeout(fetchReviews, 300) }

function formatDate(d) { return d ? new Date(d).toLocaleDateString() : '—' }

function canFollowUp(review) {
  if (!authStore.user) return false
  if (review.reviewer_id !== authStore.user.id) return false
  if (review.is_followup) return false
  const diff = Date.now() - new Date(review.created_at).getTime()
  return diff <= 14 * 24 * 60 * 60 * 1000
}

async function fetchReviews() {
  loading.value = true
  try {
    const params = { skip: filters.skip, limit: filters.limit, sort_by: filters.sort_by }
    if (filters.search) params.search = filters.search
    if (filters.subject_type) params.subject_type = filters.subject_type
    if (filters.min_rating) params.rating_min = filters.min_rating
    if (filters.verified_only) params.verified_only = true
    const res = await api.get('/reviews', { params })
    reviews.value = res.data.map(r => ({ ...r, _expand: false }))
    total.value = Number(res.headers['x-total-count'] || res.data.length)
  } finally { loading.value = false }
}

async function fetchSummary() {
  try {
    const res = await api.get('/reviews/summary', {
      params: { subject_type: filters.subject_type || undefined }
    })
    summary.value = res.data
  } catch { summary.value = null }
}

function prevPage() { if (filters.skip > 0) { filters.skip = Math.max(0, filters.skip - filters.limit); fetchReviews() } }
function nextPage() { filters.skip += filters.limit; fetchReviews() }

function openCreate() {
  createForm.value = { subject_type: '', subject_id: null, subject_text: '', order_id: null, rating: 0, comment: '' }
  tagsInput.value = ''
  selectedImages.value = []
  createError.value = ''
  cooldownSeconds.value = 0
  clearInterval(_cooldownTimer)
  showCreate.value = true
}

// Re-evaluate cooldown whenever the user changes the order_id field
watch(() => createForm.value.order_id, (newId) => {
  clearInterval(_cooldownTimer)
  if (newId) {
    _checkCooldown(newId)
  } else {
    cooldownSeconds.value = 0
  }
})

function handleImageSelect(e) {
  const files = Array.from(e.target.files)
  const allowed = ['image/jpeg', 'image/png']
  const valid = files.filter(f => allowed.includes(f.type))
  if (selectedImages.value.length + valid.length > 6) {
    alert('Maximum 6 images allowed')
    return
  }
  valid.forEach(f => {
    const reader = new FileReader()
    reader.onload = e2 => selectedImages.value.push({ file: f, preview: e2.target.result })
    reader.readAsDataURL(f)
  })
}

function removeImage(i) { selectedImages.value.splice(i, 1) }

async function handleCreate() {
  createError.value = ''
  if (!createForm.value.subject_type) { createError.value = 'Please select a subject type.'; return }
  // exam_type requires subject_text; all other types require subject_id
  if (createForm.value.subject_type === 'exam_type') {
    if (!createForm.value.subject_text?.trim()) {
      createError.value = 'Exam type name is required for exam type reviews.'
      return
    }
  } else {
    if (!createForm.value.subject_id) {
      createError.value = 'Subject ID is required.'
      return
    }
  }
  if (!createForm.value.rating) { createError.value = 'Please select a rating.'; return }
  if (createForm.value.comment.length < 1) { createError.value = 'Comment is required.'; return }

  // Client-side cooldown gate
  const orderId = createForm.value.order_id
  if (orderId && cooldownSeconds.value > 0) {
    createError.value = `Please wait ${fmtCooldown(cooldownSeconds.value)} before submitting another review for this order.`
    return
  }

  creating.value = true
  try {
    const tags = tagsInput.value ? tagsInput.value.split(',').map(t => t.trim()).filter(Boolean) : []
    // Build payload: exam_type sends subject_text; other types send subject_id
    const payload = {
      subject_type: createForm.value.subject_type,
      order_id: orderId || null,
      rating: createForm.value.rating,
      comment: createForm.value.comment,
      tags: tags.length ? JSON.stringify(tags) : null,
    }
    if (createForm.value.subject_type === 'exam_type') {
      payload.subject_text = createForm.value.subject_text.trim()
    } else {
      payload.subject_id = createForm.value.subject_id
    }
    const res = await api.post('/reviews', payload)
    // Record cooldown for this order immediately after a successful submission
    if (orderId) _recordCooldown(orderId)

    // Upload images sequentially
    for (const img of selectedImages.value) {
      const fd = new FormData()
      fd.append('file', img.file)
      await api.post(`/reviews/${res.data.id}/images`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    }
    showCreate.value = false
    await fetchReviews()
  } catch (err) {
    createError.value = err.response?.data?.detail || 'Failed to submit review.'
  } finally { creating.value = false }
}

function openFollowup(review) {
  followupTarget.value = review
  followupForm.value = { rating: review.rating, comment: '' }
  followupError.value = ''
  showFollowup.value = true
}

async function handleFollowup() {
  followupError.value = ''
  if (!followupForm.value.rating) { followupError.value = 'Select a rating.'; return }
  submittingFollowup.value = true
  try {
    await api.post(`/reviews/${followupTarget.value.id}/followup`, followupForm.value)
    showFollowup.value = false
    await fetchReviews()
  } catch (err) {
    followupError.value = err.response?.data?.detail || 'Failed to submit follow-up.'
  } finally { submittingFollowup.value = false }
}

async function togglePin(review) {
  const endpoint = review.is_pinned ? 'unpin' : 'pin'
  await api.patch(`/reviews/${review.id}/${endpoint}`, { note: null })
  review.is_pinned = !review.is_pinned
}

function toggleCollapse(review) {
  if (review.is_collapsed) {
    uncollapseReview(review)
  } else {
    collapseTarget.value = review
    moderationNote.value = ''
    showCollapseNote.value = true
  }
}

async function confirmCollapse() {
  await api.patch(`/reviews/${collapseTarget.value.id}/collapse`, { note: moderationNote.value || null })
  collapseTarget.value.is_collapsed = true
  collapseTarget.value.moderation_note = moderationNote.value
  showCollapseNote.value = false
}

async function uncollapseReview(review) {
  await api.patch(`/reviews/${review.id}/uncollapse`, { note: null })
  review.is_collapsed = false
}

async function deleteReview(review) {
  if (!confirm('Delete this review permanently?')) return
  await api.delete(`/reviews/${review.id}`)
  reviews.value = reviews.value.filter(r => r.id !== review.id)
}

onMounted(async () => {
  await Promise.all([fetchReviews(), fetchSummary()])
})

onUnmounted(() => {
  clearInterval(_cooldownTimer)
})
</script>
