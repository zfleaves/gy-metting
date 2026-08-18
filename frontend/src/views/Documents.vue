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
    <CreateMeetingModal
      :visible="showModal"
      :editing-id="editingId"
      :edit-data="editingId ? form : null"
      @close="closeModal"
      @saved="onMeetingSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  listMeetings, deleteMeeting, listYuqueRecords,
} from '../api.js'
import CreateMeetingModal from '../components/CreateMeetingModal.vue'
import { toast } from '../toast.js'

const router = useRouter()

const meetings = ref([])
const loading = ref(true)
const searchQuery = ref('')

// 弹窗
const showModal = ref(false)
const editingId = ref(null)
const form = ref({ title: '', background: '', snapshot_ids: [] })

const filteredMeetings = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return meetings.value
  return meetings.value.filter(m => m.title.toLowerCase().includes(q))
})

onMounted(async () => {
  try { meetings.value = await listMeetings() } catch { /* ignore */ }
  finally { loading.value = false }
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
  showModal.value = true
}

function openEditModal(m) {
  editingId.value = m.id
  form.value = {
    title: m.title,
    background: m.background || '',
    snapshot_ids: m.snapshot_ids || [],
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingId.value = null
}

async function onMeetingSaved() {
  meetings.value = await listMeetings()
  closeModal()
}

async function doDelete(m) {
  if (!confirm(`确定删除会议「${m.title}」？`)) return
  try {
    await deleteMeeting(m.id)
    meetings.value = meetings.value.filter(item => item.id !== m.id)
  } catch (e) {
    toast.error('删除失败: ' + (e.message || '未知错误'))
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