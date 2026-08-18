<template>
  <div v-if="visible" class="modal-overlay" @click.self="cancel">
    <div class="modal">
      <h3>{{ editingId ? '编辑会议' : '新建会议' }}</h3>

      <div class="field">
        <label>会议标题 <span class="required">*</span></label>
        <input v-model="form.title" type="text" placeholder="如：SCPRO-1071 需求评审" />
      </div>

      <div class="field">
        <label>业务背景</label>
        <textarea v-model="form.background" class="bg-input" placeholder="输入本次会议的业务背景、讨论要点、特殊要求等..." rows="4"></textarea>
      </div>

      <!-- 关联资源 -->
      <div class="field">
        <label>关联参考文档</label>
        <div class="resource-tabs">
          <button class="res-tab" :class="{ active: resTab === 'upload' }" @click="resTab = 'upload'">📤 本地上传</button>
          <button class="res-tab" :class="{ active: resTab === 'yuque' }" @click="resTab = 'yuque'">🦜 语雀拉取</button>
          <button class="res-tab" :class="{ active: resTab === 'records' }" @click="resTab = 'records'">📋 拉取记录</button>
        </div>

        <!-- 本地上传 -->
        <div v-if="resTab === 'upload'" class="res-panel">
          <div class="upload-row">
            <input type="file" ref="fileInput" accept=".docx,.pdf,.txt,.md" @change="onFileSelect" hidden />
            <button class="btn-upload" @click="$refs.fileInput.click()" :disabled="uploading">
              {{ uploading ? '上传中...' : '选择文件上传' }}
            </button>
            <span v-if="uploadError" class="upload-error">{{ uploadError }}</span>
          </div>
        </div>

        <!-- 语雀拉取 -->
        <div v-if="resTab === 'yuque'" class="res-panel">
          <div class="yuque-form">
            <select v-model="yuqueSourceId" class="input-sm">
              <option value="">-- 选择语雀来源 --</option>
              <option v-for="s in yuqueSources" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
            <input v-model="yuqueRequirementId" class="input-sm" placeholder="需求号，如 SCPRO-1071" />
            <button class="btn-upload" @click="doYuquePull" :disabled="!yuqueSourceId || !yuqueRequirementId || yuquePulling">
              {{ yuquePulling ? '拉取中...' : '拉取' }}
            </button>
          </div>
          <div v-if="yuqueError" class="upload-error">{{ yuqueError }}</div>
        </div>

        <!-- 拉取记录 -->
        <div v-if="resTab === 'records'" class="res-panel">
          <div v-if="!pullRecords.length" class="empty-hint">暂无拉取记录，请先拉取需求</div>
          <div v-for="rec in pullRecords" :key="rec.id" class="record-item" :class="{ selected: recordCheckState(rec) === 'all' }">
            <div class="record-item-header" @click="toggleRecord(rec)">
              <span class="record-arrow" :class="{ open: rec._expanded }">▶</span>
              <span class="record-check" @click.stop="toggleAllDocs(rec)">{{ recordCheckIcon(rec) }}</span>
              <div class="record-item-left">
                <strong>{{ rec.requirement_id }}</strong>
                <span class="source-tag">{{ rec.source_name }}</span>
              </div>
              <div class="record-item-right">
                <span class="doc-count-badge">{{ rec.success }}/{{ rec.total }} 文档</span>
                <span class="status-dot" :class="'dot-' + rec.status"></span>
              </div>
            </div>
            <div v-if="rec._expanded" class="record-docs">
              <div v-for="d in rec.results" :key="d.slug" class="record-doc" :class="{ selected: form.snapshot_ids.includes(d.id) }" @click.stop="toggleDoc(d.id)">
                <span class="doc-check">{{ form.snapshot_ids.includes(d.id) ? '✅' : '📄' }}</span>
                <span class="doc-name">{{ d.title }}</span>
                <span v-if="d.status === 'failed'" class="doc-fail">失败</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 已选文档总览 -->
      <div v-if="selectedDocList.length" class="selected-summary">
        <div class="summary-title">
          已选文档（{{ selectedDocList.length }} 个）
          <span class="summary-hint">来自各标签页的添加</span>
        </div>
        <div class="summary-list">
          <div v-for="item in selectedDocList" :key="item.id" class="summary-item">
            <span class="snap-icon">{{ item.source_type === 'yuque' ? '🦜' : '📄' }}</span>
            <span class="snap-title">{{ item.title }}</span>
            <button class="btn-remove" @click="removeDoc(item.id)">✕</button>
          </div>
        </div>
      </div>

      <div v-if="modalError" class="modal-error">{{ modalError }}</div>

      <div class="modal-actions">
        <button class="btn-cancel" @click="cancel">取消</button>
        <button class="btn-save" @click="save" :disabled="saving">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { createMeeting, updateMeeting, uploadDocument, listDocuments, listYuqueSources, pullYuqueRequirement, listYuqueRecords } from '../api.js'

const props = defineProps({
  visible: Boolean,
  editingId: { type: String, default: null },
  editData: { type: Object, default: null },
})

const emit = defineEmits(['close', 'saved'])

const form = ref({ title: '', background: '', snapshot_ids: [] })
const resTab = ref('upload')
const saving = ref(false)
const modalError = ref('')

// 上传
const fileInput = ref(null)
const uploading = ref(false)
const uploadError = ref('')

// 语雀
const yuqueSources = ref([])
const yuqueSourceId = ref('')
const yuqueRequirementId = ref('')
const yuquePulling = ref(false)
const yuqueError = ref('')
const pullRecords = ref([])
const allSnapshots = ref([])

const selectedDocList = computed(() => {
  const ids = form.value.snapshot_ids
  if (!ids.length) return []
  const fromSnapshots = allSnapshots.value.filter(s => ids.includes(s.id))
  const fromRecords = []
  for (const rec of pullRecords.value) {
    if (rec.results) {
      for (const r of rec.results) {
        if (r.id && ids.includes(r.id)) {
          fromRecords.push({ id: r.id, title: r.title, source_type: 'yuque' })
        }
      }
    }
  }
  const seen = new Set()
  return [...fromSnapshots, ...fromRecords].filter(item => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
})

watch(() => props.visible, (v) => {
  if (v) {
    loadData()
    if (props.editingId && props.editData) {
      form.value = {
        title: props.editData.title,
        background: props.editData.background || '',
        snapshot_ids: props.editData.snapshot_ids || [],
      }
    } else {
      form.value = { title: '', background: '', snapshot_ids: [] }
    }
    modalError.value = ''
  }
})

async function loadData() {
  try { allSnapshots.value = await listDocuments() } catch { /* ignore */ }
  try { yuqueSources.value = await listYuqueSources() } catch { /* ignore */ }
  try { pullRecords.value = (await listYuqueRecords()).map(r => ({ ...r, _expanded: false })) } catch { /* ignore */ }
}

function cancel() {
  emit('close')
}

function toggleDoc(id) {
  const idx = form.value.snapshot_ids.indexOf(id)
  if (idx >= 0) form.value.snapshot_ids.splice(idx, 1)
  else form.value.snapshot_ids.push(id)
}

function toggleRecord(rec) {
  rec._expanded = !rec._expanded
}

function recordCheckState(rec) {
  const okDocs = (rec.results || []).filter(d => d.status === 'ok' && d.id)
  const selected = okDocs.filter(d => form.value.snapshot_ids.includes(d.id))
  if (!okDocs.length || !selected.length) return 'none'
  if (selected.length === okDocs.length) return 'all'
  return 'half'
}

function recordCheckIcon(rec) {
  const state = recordCheckState(rec)
  if (state === 'all') return '✅'
  if (state === 'half') return '☑️'
  return '⬜'
}

function toggleAllDocs(rec) {
  const okDocs = (rec.results || []).filter(d => d.status === 'ok' && d.id)
  const state = recordCheckState(rec)
  if (state === 'all') {
    for (const d of okDocs) {
      const idx = form.value.snapshot_ids.indexOf(d.id)
      if (idx >= 0) form.value.snapshot_ids.splice(idx, 1)
    }
  } else {
    for (const d of okDocs) {
      if (!form.value.snapshot_ids.includes(d.id)) {
        form.value.snapshot_ids.push(d.id)
      }
    }
  }
}

function removeDoc(id) {
  const idx = form.value.snapshot_ids.indexOf(id)
  if (idx >= 0) form.value.snapshot_ids.splice(idx, 1)
}

function onFileSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  uploadError.value = ''
  const allowed = ['docx', 'pdf', 'txt', 'md']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!allowed.includes(ext)) { uploadError.value = `不支持 .${ext}`; return }
  uploading.value = true
  uploadDocument(file).then(result => {
    allSnapshots.value.unshift(result)
    form.value.snapshot_ids.push(result.id)
  }).catch(e => {
    uploadError.value = e.message || '上传失败'
  }).finally(() => {
    uploading.value = false
  })
}

async function doYuquePull() {
  if (!yuqueSourceId.value || !yuqueRequirementId.value.trim()) return
  yuquePulling.value = true
  yuqueError.value = ''
  try {
    const result = await pullYuqueRequirement(yuqueSourceId.value, yuqueRequirementId.value.trim())
    allSnapshots.value = await listDocuments()
    if (result.results) {
      for (const r of result.results) {
        if (r.status === 'ok' && r.id && !form.value.snapshot_ids.includes(r.id)) {
          form.value.snapshot_ids.push(r.id)
        }
      }
    }
  } catch (e) {
    yuqueError.value = e.message || '拉取失败'
  } finally {
    yuquePulling.value = false
  }
}

async function save() {
  if (!form.value.title.trim()) {
    modalError.value = '请输入会议标题'
    return
  }
  saving.value = true
  modalError.value = ''
  try {
    const data = {
      title: form.value.title,
      background: form.value.background,
      snapshot_ids: form.value.snapshot_ids,
    }
    let result
    if (props.editingId) {
      await updateMeeting(props.editingId, data)
      result = { id: props.editingId }
    } else {
      result = await createMeeting(data)
    }
    emit('saved', result)
  } catch (e) {
    modalError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; width: 640px; max-width: 95vw; max-height: 90vh; overflow-y: auto; padding: 28px 32px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.modal h3 { margin: 0 0 20px; font-size: 1.1rem; color: #1e293b; }
.modal .field { margin-bottom: 16px; }
.modal .field label { display: block; font-size: 0.82rem; color: #64748b; margin-bottom: 4px; font-weight: 500; }
.modal .field .required { color: #dc2626; }
.modal input[type="text"], .modal textarea { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.85rem; outline: none; box-sizing: border-box; font-family: inherit; }
.modal input[type="text"]:focus, .modal textarea:focus { border-color: #4f46e5; }
.modal .bg-input { resize: vertical; min-height: 80px; }

.resource-tabs { display: flex; gap: 4px; margin-bottom: 8px; flex-wrap: wrap; }
.res-tab { padding: 5px 14px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.8rem; color: #64748b; }
.res-tab.active { border-color: #4f46e5; color: #4f46e5; background: #eef2ff; }
.res-tab:hover { border-color: #4f46e5; }
.res-panel { min-height: 60px; }
.upload-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.btn-upload { padding: 6px 16px; border: 1px solid #4f46e5; background: #fff; color: #4f46e5; border-radius: 6px; cursor: pointer; font-size: 0.8rem; }
.btn-upload:hover { background: #eef2ff; }
.btn-upload:disabled { opacity: 0.5; cursor: not-allowed; }
.upload-error { color: #dc2626; font-size: 0.78rem; }
.yuque-form { display: flex; gap: 8px; flex-wrap: wrap; }
.input-sm { padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.82rem; outline: none; }
.input-sm:focus { border-color: #4f46e5; }

.empty-hint { color: #94a3b8; font-size: 0.82rem; padding: 12px 0; }
.record-item { border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 6px; overflow: hidden; }
.record-item.selected { border-color: #4f46e5; }
.record-item-header { display: flex; align-items: center; gap: 8px; padding: 8px 10px; cursor: pointer; }
.record-item-header:hover { background: #f8fafc; }
.record-arrow { font-size: 0.7rem; color: #94a3b8; transition: transform 0.15s; }
.record-arrow.open { transform: rotate(90deg); }
.record-check { font-size: 0.85rem; cursor: pointer; }
.record-item-left { flex: 1; display: flex; align-items: center; gap: 6px; }
.record-item-left strong { font-size: 0.85rem; color: #1e293b; }
.source-tag { font-size: 0.7rem; background: #eef2ff; color: #4f46e5; padding: 1px 6px; border-radius: 3px; }
.record-item-right { display: flex; align-items: center; gap: 8px; }
.doc-count-badge { font-size: 0.72rem; color: #64748b; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-success { background: #16a34a; }
.dot-partial { background: #d97706; }
.dot-failed { background: #dc2626; }
.record-docs { border-top: 1px solid #e2e8f0; padding: 4px 0; }
.record-doc { display: flex; align-items: center; gap: 6px; padding: 6px 14px; cursor: pointer; font-size: 0.82rem; }
.record-doc:hover { background: #f8fafc; }
.record-doc.selected { background: #eef2ff; }
.doc-check { font-size: 0.85rem; }
.doc-name { color: #334155; }
.doc-fail { color: #dc2626; font-size: 0.7rem; }

.selected-summary { margin-top: 12px; padding: 12px; background: #f8fafc; border-radius: 8px; }
.summary-title { font-size: 0.82rem; color: #1e293b; font-weight: 500; margin-bottom: 8px; }
.summary-hint { font-weight: 400; color: #94a3b8; font-size: 0.75rem; margin-left: 6px; }
.summary-list { display: flex; flex-wrap: wrap; gap: 6px; }
.summary-item { display: flex; align-items: center; gap: 4px; padding: 4px 10px; background: #fff; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.78rem; }
.snap-icon { font-size: 0.85rem; }
.snap-title { color: #334155; }
.btn-remove { width: 18px; height: 18px; border: none; background: #e2e8f0; border-radius: 50%; cursor: pointer; font-size: 0.65rem; color: #64748b; display: flex; align-items: center; justify-content: center; }
.btn-remove:hover { background: #dc2626; color: #fff; }

.modal-error { color: #dc2626; background: #fef2f2; padding: 8px 12px; border-radius: 6px; font-size: 0.82rem; margin-bottom: 12px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 16px; }
.btn-cancel { padding: 8px 20px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #64748b; }
.btn-cancel:hover { border-color: #dc2626; color: #dc2626; }
.btn-save { padding: 8px 20px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.btn-save:hover { background: #4338ca; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
</style>