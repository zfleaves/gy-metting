<template>
  <div class="doc-page">
    <div class="page-header">
      <h1>参考文档</h1>
      <p>上传本地文档，作为会议评审基线</p>
    </div>

    <div class="tabs">
      <button class="tab active">📤 上传文档</button>
    </div>

    <div class="tab-panel">
      <div class="upload-zone"
        :class="{ dragging }"
        @dragover.prevent="dragging = true"
        @dragleave.prevent="dragging = false"
        @drop.prevent="onDrop"
      >
        <div v-if="!uploading" class="upload-prompt">
          <p>拖拽文档到此处，或点击选择</p>
          <p class="hint">支持 docx / pdf / txt / md，最大 20MB</p>
          <input type="file" ref="fileInput" accept=".docx,.pdf,.txt,.md" @change="onFileSelect" hidden />
          <button class="btn-select" @click="$refs.fileInput.click()">选择文件</button>
        </div>
        <div v-else class="upload-progress">
          <div class="spinner"></div>
          <p>解析中...</p>
        </div>
      </div>
      <div v-if="uploadError" class="error-msg">{{ uploadError }}</div>
    </div>

    <div v-if="docs.length" class="doc-list">
      <h3>已添加的文档（{{ docs.length }}）</h3>
      <div v-for="doc in docs" :key="doc.id" class="doc-item">
        <div class="doc-info" @click="previewDoc(doc)">
          <span class="doc-icon">{{ doc.source_type === 'yuque' ? '🦜' : '📄' }}</span>
          <span class="doc-title">{{ doc.title }}</span>
          <span class="doc-type tag">{{ doc.source_type }}</span>
          <span v-if="doc.size_bytes" class="doc-size">{{ (doc.size_bytes / 1024).toFixed(1) }} KB</span>
        </div>
        <button class="btn-del" @click="removeDoc(doc)" title="删除">🗑</button>
      </div>
    </div>

    <div v-if="previewing" class="modal-overlay" @click="previewing = null">
      <div class="modal-box preview-box" @click.stop>
        <div class="preview-header">
          <h3>{{ previewing.title }}</h3>
          <button class="btn-close" @click="previewing = null">✕</button>
        </div>
        <div class="preview-body" v-text="previewContent"></div>
      </div>
    </div>

    <div class="background-section">
      <h3>业务背景</h3>
      <textarea v-model="background" class="bg-textarea" placeholder="输入本次会议的业务背景、讨论要点、特殊要求等..." rows="5"></textarea>
      <button class="btn-primary" @click="saveBackground" :disabled="bgSaving">
        {{ bgSaving ? '保存中...' : '保存背景' }}
      </button>
      <span v-if="bgSaved" class="saved-hint">✓ 已保存</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { uploadDocument, listDocuments, getDocument, deleteDocument, createMeeting, updateMeeting, listMeetings } from '../api.js'

const dragging = ref(false)
const uploading = ref(false)
const uploadError = ref('')
const docs = ref([])
const fileInput = ref(null)
const previewing = ref(null)
const previewContent = ref('')
const background = ref('')
const bgSaving = ref(false)
const bgSaved = ref(false)
let meetingId = null

onMounted(async () => {
  try { docs.value = await listDocuments() } catch { /* ignore */ }
  try {
    const meetings = await listMeetings()
    if (meetings.length) {
      meetingId = meetings[0].id
      background.value = meetings[0].background || ''
    }
  } catch { /* ignore */ }
})

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) uploadFile(file)
}
function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) uploadFile(file)
}

async function uploadFile(file) {
  uploadError.value = ''
  const allowed = ['docx', 'pdf', 'txt', 'md']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!allowed.includes(ext)) { uploadError.value = `不支持的格式: .${ext}`; return }
  if (file.size > 20 * 1024 * 1024) { uploadError.value = '文件过大，限制 20MB'; return }
  uploading.value = true
  try {
    const result = await uploadDocument(file)
    docs.value.unshift(result)
  } catch (e) { uploadError.value = '上传失败: ' + (e.message || '未知错误') }
  finally { uploading.value = false }
}

async function previewDoc(doc) {
  previewing.value = doc
  previewContent.value = ''
  try { const d = await getDocument(doc.id); previewContent.value = d.content || '(无内容)' } catch { previewContent.value = '(加载失败)' }
}

async function removeDoc(doc) {
  try { await deleteDocument(doc.id); docs.value = docs.value.filter(d => d.id !== doc.id) } catch (e) { alert('删除失败: ' + (e.message || '未知错误')) }
}

async function saveBackground() {
  bgSaving.value = true; bgSaved.value = false
  try {
    if (meetingId) { await updateMeeting(meetingId, { background: background.value }) }
    else { const m = await createMeeting({ title: '新会议', background: background.value }); meetingId = m.id }
    bgSaved.value = true; setTimeout(() => { bgSaved.value = false }, 2000)
  } catch (e) { alert('保存失败: ' + (e.message || '未知错误')) }
  finally { bgSaving.value = false }
}
</script>

<style scoped>
.doc-page { padding: 24px; max-width: 800px; }
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }
.tabs { display: flex; gap: 4px; margin-bottom: 16px; background: #f1f5f9; border-radius: 8px; padding: 4px; }
.tab { flex: 1; padding: 10px; border: none; background: none; border-radius: 6px; font-size: 0.9rem; cursor: default; color: #1e293b; font-weight: 500; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
.tab-panel { margin-bottom: 20px; }
.upload-zone { border: 2px dashed #cbd5e1; border-radius: 10px; padding: 32px; text-align: center; transition: border-color 0.2s; }
.upload-zone.dragging { border-color: #4f46e5; background: #eef2ff; }
.upload-prompt p { color: #64748b; margin-bottom: 4px; }
.hint { font-size: 0.8rem; color: #94a3b8; margin-bottom: 12px; }
.btn-select, .btn-primary { padding: 8px 20px; border-radius: 6px; font-size: 0.9rem; border: none; cursor: pointer; }
.btn-select { background: #f1f5f9; color: #334155; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.spinner { width: 32px; height: 32px; border: 3px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 12px; }
@keyframes spin { to { transform: rotate(360deg); } }
.error-msg { color: #dc2626; background: #fef2f2; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; margin-top: 8px; }
.doc-list { margin-bottom: 24px; }
.doc-list h3 { font-size: 0.95rem; color: #334155; margin: 0 0 12px; }
.doc-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 6px; }
.doc-info { display: flex; align-items: center; gap: 10px; flex: 1; min-width: 0; cursor: pointer; }
.doc-icon { font-size: 1.1rem; }
.doc-title { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 0.9rem; color: #1e293b; }
.doc-type { background: #e0e7ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
.doc-size { color: #94a3b8; font-size: 0.8rem; }
.tag { background: #e0e7ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; }
.btn-del { background: none; border: 1px solid #e2e8f0; border-radius: 4px; padding: 3px 8px; cursor: pointer; opacity: 0.5; font-size: 0.85rem; }
.btn-del:hover { opacity: 1; border-color: #dc2626; }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; max-width: 700px; width: 90%; max-height: 80vh; display: flex; flex-direction: column; box-shadow: 0 8px 30px rgba(0,0,0,0.15); }
.preview-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }
.preview-header h3 { margin: 0; font-size: 1rem; color: #1e293b; }
.btn-close { background: none; border: none; font-size: 1.2rem; cursor: pointer; color: #94a3b8; }
.preview-body { padding: 20px; overflow-y: auto; white-space: pre-wrap; font-size: 0.9rem; color: #334155; line-height: 1.7; flex: 1; }
.background-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; }
.background-section h3 { margin: 0 0 12px; font-size: 0.95rem; color: #334155; }
.bg-textarea { width: 100%; padding: 12px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; font-family: inherit; resize: vertical; outline: none; box-sizing: border-box; }
.bg-textarea:focus { border-color: #4f46e5; }
.background-section .btn-primary { margin-top: 12px; }
.saved-hint { color: #16a34a; font-size: 0.85rem; margin-left: 12px; }
</style>