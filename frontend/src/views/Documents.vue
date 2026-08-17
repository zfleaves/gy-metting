<template>
  <div class="meetings-page">
    <div class="page-header">
      <h1>参考文档</h1>
      <p>创建会议/需求记录，关联业务背景和参考文档，供音频转写时选择</p>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <input v-model="searchQuery" class="search-input" placeholder="搜索会议标题..." />
      <button class="btn-add" @click="openCreateModal">+ 新建会议</button>
    </div>

    <!-- 会议列表 -->
    <div class="table-wrap">
      <table class="meeting-table">
        <thead>
          <tr>
            <th>#</th>
            <th>会议标题</th>
            <th>业务背景</th>
            <th>关联文档</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="6" class="empty-cell">加载中...</td></tr>
          <tr v-else-if="!filteredMeetings.length"><td colspan="6" class="empty-cell">暂无会议，点击「新建会议」创建</td></tr>
          <tr v-for="(m, idx) in filteredMeetings" :key="m.id">
            <td class="cell-idx">{{ idx + 1 }}</td>
            <td><strong>{{ m.title }}</strong></td>
            <td class="cell-bg" :title="m.background">{{ m.background || '-' }}</td>
            <td class="cell-center">
              <span class="doc-count">{{ m.snapshot_ids?.length || 0 }}</span> 个
            </td>
            <td class="time-cell">{{ formatTime(m.created_at) }}</td>
            <td>
              <div class="action-btns">
                <button class="btn-detail" @click="goDetail(m.id)">详情</button>
                <button class="btn-edit" @click="openEditModal(m)">编辑</button>
                <button class="btn-del" @click="doDelete(m)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新建/编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
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
            <div
              v-for="rec in pullRecords"
              :key="rec.id"
              class="record-item"
              :class="{ selected: recordCheckState(rec) === 'all' }"
            >
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
                <div v-for="d in rec.results" :key="d.slug" class="record-doc" :class="{ selected: form.snapshot_ids.includes(d.id) }" @click.stop="toggleDocInRecord(d)">
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
          <button class="btn-cancel" @click="closeModal">取消</button>
          <button class="btn-save" @click="saveMeeting" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  listMeetings, createMeeting, updateMeeting, deleteMeeting,
  uploadDocument, listDocuments,
  listYuqueSources, pullYuqueRequirement, listYuqueRecords,
} from '../api.js'

const router = useRouter()

const meetings = ref([])
const allSnapshots = ref([])
const yuqueSources = ref([])
const pullRecords = ref([])
const loading = ref(true)
const searchQuery = ref('')

// 弹窗
const showModal = ref(false)
const editingId = ref(null)
const saving = ref(false)
const modalError = ref('')
const form = ref({ title: '', background: '', snapshot_ids: [] })
const resTab = ref('upload')

// 上传
const fileInput = ref(null)
const uploading = ref(false)
const uploadError = ref('')

// 语雀拉取
const yuqueSourceId = ref('')
const yuqueRequirementId = ref('')
const yuquePulling = ref(false)
const yuqueError = ref('')

const filteredMeetings = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return meetings.value
  return meetings.value.filter(m => m.title.toLowerCase().includes(q))
})

// 从所有已选 snapshot_ids 中收集文档信息
const selectedDocList = computed(() => {
  const ids = form.value.snapshot_ids
  if (!ids.length) return []
  // 从 allSnapshots 中查找
  const fromSnapshots = allSnapshots.value.filter(s => ids.includes(s.id))
  // 从拉取记录的结果中查找
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
  // 合并去重
  const seen = new Set()
  return [...fromRecords, ...fromSnapshots].filter(item => {
    if (seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
})

// 拉取记录勾选状态
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
  // 点击勾选框：全选/取消全选
  const okDocs = (rec.results || []).filter(d => d.status === 'ok' && d.id)
  const state = recordCheckState(rec)
  if (state === 'all') {
    // 全部已选 → 取消全部
    for (const d of okDocs) {
      const idx = form.value.snapshot_ids.indexOf(d.id)
      if (idx >= 0) form.value.snapshot_ids.splice(idx, 1)
    }
  } else {
    // 未选或半选 → 全选
    for (const d of okDocs) {
      if (!form.value.snapshot_ids.includes(d.id)) {
        form.value.snapshot_ids.push(d.id)
      }
    }
  }
}

onMounted(async () => {
  try { meetings.value = await listMeetings() } catch { /* ignore */ }
  finally { loading.value = false }
  try { allSnapshots.value = await listDocuments() } catch { /* ignore */ }
  try { yuqueSources.value = await listYuqueSources() } catch { /* ignore */ }
  try {
    pullRecords.value = (await listYuqueRecords()).map(r => ({ ...r, _expanded: false }))
  } catch { /* ignore */ }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function goDetail(id) {
  router.push(`/meeting/${id}`)
}

function openCreateModal() {
  editingId.value = null
  form.value = { title: '', background: '', snapshot_ids: [] }
  resTab.value = 'upload'
  modalError.value = ''
  showModal.value = true
}

function openEditModal(m) {
  editingId.value = m.id
  form.value = {
    title: m.title,
    background: m.background || '',
    snapshot_ids: m.snapshot_ids || [],
  }
  resTab.value = 'snapshots'
  modalError.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingId.value = null
}

function toggleRecord(rec) {
  // 点击拉取记录：展开/收起，如果已展开则收起
  rec._expanded = !rec._expanded
}

function toggleDocInRecord(doc) {
  // 点选/取消某个文档
  const idx = form.value.snapshot_ids.indexOf(doc.id)
  if (idx >= 0) {
    form.value.snapshot_ids.splice(idx, 1)
  } else {
    form.value.snapshot_ids.push(doc.id)
  }
}

function removeDoc(id) {
  const idx = form.value.snapshot_ids.indexOf(id)
  if (idx >= 0) form.value.snapshot_ids.splice(idx, 1)
}

async function onFileSelect(e) {
  const file = e.target.files[0]
  if (!file) return
  uploadError.value = ''
  const allowed = ['docx', 'pdf', 'txt', 'md']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!allowed.includes(ext)) { uploadError.value = `不支持 .${ext}`; return }
  uploading.value = true
  try {
    const result = await uploadDocument(file)
    allSnapshots.value.unshift(result)
    form.value.snapshot_ids.push(result.id)
    // 自动切到快照 tab
    resTab.value = 'snapshots'
  } catch (e) {
    uploadError.value = e.message || '上传失败'
  } finally {
    uploading.value = false
  }
}

async function doYuquePull() {
  if (!yuqueSourceId.value || !yuqueRequirementId.value.trim()) return
  yuquePulling.value = true
  yuqueError.value = ''
  try {
    const result = await pullYuqueRequirement(yuqueSourceId.value, yuqueRequirementId.value.trim())
    // 刷新快照列表
    allSnapshots.value = await listDocuments()
    // 自动选中拉取的文档
    if (result.results) {
      for (const r of result.results) {
        if (r.status === 'ok' && r.id && !form.value.snapshot_ids.includes(r.id)) {
          form.value.snapshot_ids.push(r.id)
        }
      }
    }
    resTab.value = 'snapshots'
  } catch (e) {
    yuqueError.value = e.message || '拉取失败'
  } finally {
    yuquePulling.value = false
  }
}

async function saveMeeting() {
  modalError.value = ''
  if (!form.value.title.trim()) {
    modalError.value = '请输入会议标题'
    return
  }
  saving.value = true
  try {
    const data = {
      title: form.value.title,
      background: form.value.background,
      snapshot_ids: form.value.snapshot_ids,
    }
    if (editingId.value) {
      await updateMeeting(editingId.value, data)
    } else {
      await createMeeting(data)
    }
    meetings.value = await listMeetings()
    closeModal()
  } catch (e) {
    modalError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function doDelete(m) {
  if (!confirm(`确定删除会议「${m.title}」？`)) return
  try {
    await deleteMeeting(m.id)
    meetings.value = meetings.value.filter(item => item.id !== m.id)
  } catch (e) {
    alert('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.meetings-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.search-input { flex: 1; max-width: 320px; padding: 8px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; }
.search-input:focus { border-color: #4f46e5; }
.btn-add { padding: 8px 18px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; white-space: nowrap; }
.btn-add:hover { background: #4338ca; }

.table-wrap { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.meeting-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; table-layout: auto; }
.meeting-table thead { background: #f8fafc; }
.meeting-table th { text-align: left; padding: 10px 14px; font-weight: 600; color: #64748b; font-size: 0.82rem; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.meeting-table td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; color: #334155; }
.meeting-table tbody tr:hover { background: #f8fafc; }
.meeting-table tbody tr:last-child td { border-bottom: none; }
.empty-cell { text-align: center; color: #94a3b8; padding: 40px 14px !important; }
.cell-idx { color: #94a3b8; width: 1%; white-space: nowrap; }
.cell-center { text-align: center; }
.cell-bg { max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #64748b; }
.time-cell { color: #94a3b8; white-space: nowrap; }
.doc-count { font-weight: 600; color: #4f46e5; }

.action-btns { display: flex; gap: 6px; width: 1%; white-space: nowrap; }
.btn-detail { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #059669; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-detail:hover { background: #f0fdf4; }
.btn-edit { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #4f46e5; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-edit:hover { background: #eef2ff; }
.btn-del { padding: 4px 12px; border: 1px solid #fecaca; background: #fff; color: #dc2626; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-del:hover { background: #fef2f2; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; padding: 28px; width: 640px; max-height: 90vh; overflow-y: auto; }
.modal h3 { margin: 0 0 20px; color: #1e293b; font-size: 1.1rem; }
.field { margin-bottom: 16px; }
.field label { display: block; font-size: 0.85rem; color: #64748b; margin-bottom: 4px; }
.field .required { color: #dc2626; }
.field input, .field select, .bg-input { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; font-family: inherit; }
.field input:focus, .field select:focus, .bg-input:focus { border-color: #4f46e5; }
.bg-input { resize: vertical; }

/* 资源选项卡 */
.resource-tabs { display: flex; gap: 4px; margin-bottom: 8px; }
.res-tab { padding: 6px 14px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.82rem; color: #64748b; }
.res-tab.active { border-color: #4f46e5; color: #4f46e5; background: #eef2ff; }
.res-panel { padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; background: #f8fafc; margin-bottom: 8px; }
.upload-row { display: flex; align-items: center; gap: 8px; }
.btn-upload { padding: 6px 14px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }
.btn-upload:disabled { opacity: 0.6; cursor: not-allowed; }
.yuque-form { display: flex; gap: 6px; align-items: center; }
.input-sm { padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.82rem; outline: none; flex: 1; }
.input-sm:focus { border-color: #4f46e5; }
.upload-error { color: #dc2626; font-size: 0.8rem; margin-top: 4px; display: block; }
.empty-hint { color: #94a3b8; font-size: 0.85rem; padding: 8px 0; }

/* 拉取记录 - 树形结构 */
.record-item {
  border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 6px;
  overflow: hidden;
}
.record-item:hover { border-color: #4f46e5; }
.record-item.selected { border-color: #4f46e5; background: #eef2ff; }
.record-item-header {
  display: flex; align-items: center; gap: 8px; padding: 8px 10px;
  cursor: pointer; user-select: none;
}
.record-item-header:hover { background: #f8fafc; }
.record-item.selected .record-item-header { background: #eef2ff; }
.record-arrow { flex-shrink: 0; font-size: 0.7rem; color: #94a3b8; width: 14px; text-align: center; transition: transform 0.15s; }
.record-arrow.open { transform: rotate(90deg); }
.record-check { flex-shrink: 0; font-size: 0.9rem; }
.record-item-left { display: flex; align-items: center; gap: 6px; flex: 1; min-width: 0; }
.record-item-left strong { font-size: 0.88rem; color: #1e293b; }
.record-item-right { display: flex; align-items: center; gap: 6px; flex-shrink: 0; }
.source-tag { font-size: 0.7rem; background: #e0e7ff; color: #4f46e5; padding: 1px 6px; border-radius: 3px; }
.doc-count-badge { font-size: 0.75rem; color: #64748b; background: #f1f5f9; padding: 1px 8px; border-radius: 8px; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.dot-success { background: #16a34a; }
.dot-partial { background: #d97706; }
.dot-failed { background: #dc2626; }
.record-docs { border-top: 1px solid #e2e8f0; padding: 6px 0 6px 28px; background: #fafbfc; }
.record-doc {
  display: flex; align-items: center; gap: 6px; padding: 5px 8px; border-radius: 4px;
  font-size: 0.82rem; cursor: pointer; position: relative;
}
.record-doc::before {
  content: '├'; position: absolute; left: -16px; color: #cbd5e1; font-size: 0.7rem;
}
.record-doc:last-child::before { content: '└'; }
.record-doc:hover { background: #eef2ff; }
.record-doc.selected { background: #f0fdf4; }
.record-doc.selected::before { color: #16a34a; }
.doc-check { flex-shrink: 0; font-size: 0.85rem; }
.doc-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-fail { font-size: 0.7rem; color: #dc2626; }

.modal-error { color: #dc2626; font-size: 0.85rem; margin-bottom: 12px; padding: 8px; background: #fef2f2; border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.btn-cancel { padding: 8px 20px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-save { padding: 8px 20px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-save:disabled { opacity: 0.6; }

/* 已选文档总览 */
.selected-summary { margin-top: 4px; padding: 10px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; }
.summary-title { font-size: 0.82rem; color: #64748b; font-weight: 500; margin-bottom: 6px; }
.summary-hint { font-weight: 400; font-size: 0.75rem; color: #94a3b8; margin-left: 6px; }
.summary-list { display: flex; flex-wrap: wrap; gap: 4px; max-height: 120px; overflow-y: auto; }
.summary-item { display: flex; align-items: center; gap: 4px; padding: 3px 8px; background: #fff; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.8rem; }
.summary-item .snap-title { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.summary-item .btn-remove { background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 0.8rem; padding: 0 2px; }
.summary-item .btn-remove:hover { color: #dc2626; }
</style>