<template>
  <div class="yuque-page">
    <div class="page-header">
      <h1>语雀拉取</h1>
      <p>选择语雀来源，输入需求号拉取关联文档</p>
    </div>

    <!-- 查询 & 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <input
          v-model="searchQuery"
          class="search-input"
          placeholder="搜索来源名称..."
          @input="onSearch"
        />
      </div>
      <div class="toolbar-right">
        <button class="btn-add" @click="openAddModal">+ 新增来源</button>
      </div>
    </div>

    <!-- 来源表格 -->
    <div class="table-wrap">
      <table class="yuque-table">
        <thead>
          <tr>
            <th style="width: 80px">序号</th>
            <th style="width: 160px">名称</th>
            <th>知识库 URL</th>
            <th style="width: 150px">Token</th>
            <th style="width: 80px">Session</th>
            <th style="width: 80px">CToken</th>
            <th style="width: 140px">创建时间</th>
            <th style="width: 120px">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!filteredSources.length">
            <td colspan="8" class="empty-cell">暂无来源数据</td>
          </tr>
          <tr v-for="(s, idx) in filteredSources" :key="s.id">
            <td>{{ idx + 1 }}</td>
            <td><strong>{{ s.name }}</strong></td>
            <td class="url-cell" :title="s.yuque_url">{{ s.yuque_url || '-' }}</td>
            <td><code class="token-text">{{ s.token }}</code></td>
            <td>
              <span class="tag" :class="s.has_session ? 'tag-yes' : 'tag-no'">
                {{ s.has_session ? '有' : '无' }}
              </span>
            </td>
            <td>
              <span class="tag" :class="s.has_ctoken ? 'tag-yes' : 'tag-no'">
                {{ s.has_ctoken ? '有' : '无' }}
              </span>
            </td>
            <td class="time-cell">{{ formatTime(s.created_at) }}</td>
            <td>
              <div class="action-btns">
                <button class="btn-edit" @click="openEditModal(s)">修改</button>
                <button class="btn-del" @click="removeSource(s)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 拉取区 -->
    <div class="pull-section">
      <div class="pull-row">
        <select v-model="selectedSource" class="source-select">
          <option value="">-- 选择来源 --</option>
          <option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <input
          v-model="requirementId"
          class="pull-input"
          placeholder="输入需求号，如 SCPRO-1071 或 MOPRO-1900"
          @keyup.enter="doPull"
          :disabled="!selectedSource"
        />
        <button class="btn-pull" @click="doPull" :disabled="!selectedSource || pulling">
          <span v-if="pulling" class="spinner-sm"></span>
          {{ pulling ? '拉取中...' : '拉取需求' }}
        </button>
      </div>
      <div v-if="pullError" class="error-msg">{{ pullError }}</div>
    </div>

    <!-- 拉取结果 -->
    <div v-if="pullResult" class="result-card">
      <div class="result-header">
        <h3>拉取结果：{{ pullResult.matched_title }}</h3>
        <span class="result-count">共 {{ pullResult.total }} 个文档</span>
      </div>
      <div class="result-list">
        <div v-for="r in pullResult.results" :key="r.slug" class="result-item" :class="r.status">
          <span class="result-icon">{{ r.status === 'ok' ? '✅' : '❌' }}</span>
          <span
            v-if="r.status === 'ok' && r.id"
            class="result-title link"
            @click="previewDoc(r.id, r.title)"
          >{{ r.title }}</span>
          <span v-else class="result-title">{{ r.title }}</span>
          <span v-if="r.status === 'failed'" class="result-error">{{ r.error }}</span>
        </div>
      </div>
    </div>

    <!-- 文档预览弹窗 -->
    <div v-if="previewDocId" class="modal-overlay" @click.self="closePreview">
      <div class="preview-modal">
        <div class="preview-header">
          <div class="preview-file-info">
            <span class="preview-icon">📄</span>
            <span class="preview-filename">{{ previewTitle }}</span>
          </div>
          <button class="preview-close" @click="closePreview">✕</button>
        </div>
        <div class="preview-toolbar">
          <span class="preview-meta" v-if="previewMeta">
            {{ previewMeta.size }} 字 · {{ previewMeta.created_at }}
          </span>
          <span class="preview-status" v-if="previewLoading">加载中...</span>
        </div>
        <div class="preview-body">
          <div v-if="previewLoading" class="preview-loading">
            <div class="spinner"></div>
            <span>加载文档内容...</span>
          </div>
          <pre v-else class="preview-content">{{ previewContent }}</pre>
        </div>
      </div>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <h3>{{ editingId ? '修改来源' : '新增来源' }}</h3>
        <div class="field">
          <label>名称 <span class="required">*</span></label>
          <input v-model="form.name" type="text" placeholder="如：冲鸭" />
        </div>
        <div class="field">
          <label>知识库 URL</label>
          <input v-model="form.yuque_url" type="text" placeholder="语雀知识库 URL" />
        </div>
        <div class="field">
          <label>Token <span class="required">*</span></label>
          <input
            v-model="form.token"
            type="text"
            :placeholder="editingId ? '已配置（不可修改）' : '语雀 API Token'"
            :disabled="!!editingId"
          />
        </div>
        <div class="field-row">
          <div class="field">
            <label>Session</label>
            <input
              v-model="form.session"
              type="text"
              :placeholder="editingId ? (editingSource?.has_session ? '已设置' : '未设置') : '可选'"
              :disabled="!!editingId"
            />
          </div>
          <div class="field">
            <label>CToken</label>
            <input
              v-model="form.ctoken"
              type="text"
              :placeholder="editingId ? (editingSource?.has_ctoken ? '已设置' : '未设置') : '可选'"
              :disabled="!!editingId"
            />
          </div>
        </div>
        <div class="field">
          <label>排除关键词</label>
          <input v-model="form.exclude" type="text" placeholder="逗号分隔，可选" />
        </div>
        <div class="field-row">
          <div class="field">
            <label>附件类型</label>
            <input v-model="form.attachment_types" type="text" placeholder="可选" />
          </div>
          <div class="field">
            <label>嵌入类型</label>
            <input v-model="form.embed_types" type="text" placeholder="可选" />
          </div>
        </div>
        <div v-if="modalError" class="error-msg">{{ modalError }}</div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="closeModal">取消</button>
          <button class="btn-save" @click="saveSource" :disabled="sourceSaving">
            {{ sourceSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listYuqueSources, createYuqueSource, updateYuqueSource, deleteYuqueSource, pullYuqueRequirement, getDocument } from '../api.js'
import { toast } from '../toast.js'

const sources = ref([])
const searchQuery = ref('')
const selectedSource = ref('')
const requirementId = ref('')
const pulling = ref(false)
const pullError = ref('')
const pullResult = ref(null)

// 预览状态
const previewDocId = ref(null)
const previewTitle = ref('')
const previewContent = ref('')
const previewLoading = ref(false)
const previewMeta = ref(null)

// 弹窗状态
const showModal = ref(false)
const editingId = ref(null)
const editingSource = ref(null) // 编辑时保存原始来源数据，用于展示已设字段
const sourceSaving = ref(false)
const modalError = ref('')
const form = ref({ name: '', yuque_url: '', token: '', session: '', ctoken: '', exclude: '', attachment_types: '', embed_types: '' })

const filteredSources = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sources.value
  return sources.value.filter(s => s.name.toLowerCase().includes(q))
})

onMounted(async () => {
  try { sources.value = await listYuqueSources() } catch { /* ignore */ }
})

function onSearch() {
  // computed 自动响应
}

function openAddModal() {
  editingId.value = null
  form.value = { name: '', yuque_url: '', token: '', session: '', ctoken: '', exclude: '', attachment_types: '', embed_types: '' }
  modalError.value = ''
  showModal.value = true
}

function openEditModal(s) {
  editingId.value = s.id
  editingSource.value = s
  form.value = {
    name: s.name,
    yuque_url: s.yuque_url || '',
    token: s.token || '', // 显示 masked token（如 "abc123***"）
    session: s.has_session ? '已设置' : '',
    ctoken: s.has_ctoken ? '已设置' : '',
    exclude: s.exclude || '',
    attachment_types: s.attachment_types || '',
    embed_types: s.embed_types || '',
  }
  modalError.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingId.value = null
  editingSource.value = null
}

async function saveSource() {
  modalError.value = ''
  if (!form.value.name.trim()) {
    modalError.value = '名称不能为空'
    return
  }
  if (!editingId.value && !form.value.token.trim()) {
    modalError.value = 'Token 不能为空'
    return
  }
  sourceSaving.value = true
  try {
    if (editingId.value) {
      // 编辑时只传可修改字段，不传 token/session/ctoken（已禁用）
      await updateYuqueSource(editingId.value, {
        name: form.value.name,
        yuque_url: form.value.yuque_url,
        exclude: form.value.exclude,
        attachment_types: form.value.attachment_types,
        embed_types: form.value.embed_types,
      })
    } else {
      await createYuqueSource(form.value)
    }
    sources.value = await listYuqueSources()
    closeModal()
  } catch (e) {
    modalError.value = e.message || '保存失败'
  } finally {
    sourceSaving.value = false
  }
}

async function removeSource(s) {
  try {
    await ElMessageBox.confirm(`确定删除来源「${s.name}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteYuqueSource(s.id)
    if (selectedSource.value === s.id) selectedSource.value = ''
    sources.value = await listYuqueSources()
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}

async function doPull() {
  if (!selectedSource.value || !requirementId.value.trim()) return
  pulling.value = true
  pullError.value = ''
  pullResult.value = null
  try {
    pullResult.value = await pullYuqueRequirement(selectedSource.value, requirementId.value.trim())
    // 拉取成功后自动跳转到记录页的提示
  } catch (e) {
    pullError.value = '拉取失败: ' + (e.message || '未知错误')
  } finally {
    pulling.value = false
  }
}

async function previewDoc(id, title) {
  previewDocId.value = id
  previewTitle.value = title
  previewContent.value = ''
  previewLoading.value = true
  previewMeta.value = null
  try {
    const doc = await getDocument(id)
    previewContent.value = doc.content || '(无内容)'
    const wordCount = doc.content ? doc.content.length : 0
    previewMeta.value = {
      size: wordCount.toLocaleString(),
      created_at: formatTime(doc.created_at),
    }
  } catch (e) {
    previewContent.value = '(加载失败: ' + (e.message || '未知错误') + ')'
  } finally {
    previewLoading.value = false
  }
}

function closePreview() {
  previewDocId.value = null
  previewTitle.value = ''
  previewContent.value = ''
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}
</script>

<style scoped>
.yuque-page {
  padding: 24px;
}

.page-header {
  margin-bottom: 20px;
}
.page-header h1 {
  font-size: 1.3rem;
  color: #1e293b;
  margin: 0 0 4px;
}
.page-header p {
  color: #94a3b8;
  font-size: 0.9rem;
  margin: 0;
}

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  gap: 12px;
}
.toolbar-left {
  flex: 1;
}
.search-input {
  width: 100%;
  max-width: 320px;
  padding: 8px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
}
.search-input:focus {
  border-color: #4f46e5;
}
.btn-add {
  padding: 8px 18px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  white-space: nowrap;
}
.btn-add:hover {
  background: #4338ca;
}

/* 表格 */
.table-wrap {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 24px;
}
.yuque-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.yuque-table thead {
  background: #f8fafc;
}
.yuque-table th {
  text-align: left;
  padding: 10px 14px;
  font-weight: 600;
  color: #64748b;
  font-size: 0.82rem;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}
.yuque-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}
.yuque-table tbody tr:hover {
  background: #f8fafc;
}
.yuque-table tbody tr:last-child td {
  border-bottom: none;
}
.empty-cell {
  text-align: center;
  color: #94a3b8;
  padding: 40px 14px !important;
}
.url-cell {
  max-width: 240px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.token-text {
  font-size: 0.78rem;
  color: #94a3b8;
  background: #f1f5f9;
  padding: 2px 6px;
  border-radius: 3px;
}
.time-cell {
  color: #94a3b8;
  font-size: 0.82rem;
}

/* 标签 */
.tag {
  display: inline-block;
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}
.tag-yes {
  background: #ecfdf5;
  color: #059669;
}
.tag-no {
  background: #f1f5f9;
  color: #94a3b8;
}

/* 操作按钮 */
.action-btns {
  display: flex;
  gap: 6px;
}
.btn-edit {
  padding: 4px 12px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #4f46e5;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}
.btn-edit:hover {
  background: #eef2ff;
}
.btn-del {
  padding: 4px 12px;
  border: 1px solid #fecaca;
  background: #fff;
  color: #dc2626;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}
.btn-del:hover {
  background: #fef2f2;
}

/* 拉取区 */
.pull-section {
  margin-bottom: 24px;
}
.pull-row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.source-select {
  padding: 10px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.9rem;
  background: #fff;
  outline: none;
  min-width: 180px;
}
.source-select:focus {
  border-color: #4f46e5;
}
.pull-input {
  flex: 1;
  padding: 10px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  font-size: 0.9rem;
  outline: none;
}
.pull-input:focus {
  border-color: #4f46e5;
}
.pull-input:disabled {
  background: #f8fafc;
}
.btn-pull {
  padding: 10px 24px;
  background: #4f46e5;
  color: #fff;
  border-radius: 8px;
  font-size: 0.9rem;
  border: none;
  cursor: pointer;
  white-space: nowrap;
}
.btn-pull:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error-msg {
  color: #dc2626;
  background: #fef2f2;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-top: 8px;
}

.spinner-sm {
  width: 14px;
  height: 14px;
  border: 2px solid #e2e8f0;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  display: inline-block;
  margin-right: 6px;
  vertical-align: middle;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 拉取结果 */
.result-card {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}
.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}
.result-header h3 {
  margin: 0;
  font-size: 0.95rem;
  color: #1e293b;
}
.result-count {
  font-size: 0.8rem;
  color: #94a3b8;
}
.result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 20px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 0.9rem;
}
.result-item.ok {
  color: #334155;
}
.result-item.failed {
  color: #dc2626;
}
.result-icon {
  flex-shrink: 0;
}
.result-title {
  flex: 1;
}
.result-title.link {
  color: #4f46e5;
  cursor: pointer;
  text-decoration: none;
}
.result-title.link:hover {
  text-decoration: underline;
  color: #4338ca;
}
.result-error {
  font-size: 0.8rem;
  color: #94a3b8;
}

/* 预览弹窗 — GitHub 风格 */
.preview-modal {
  background: #fff;
  border-radius: 10px;
  width: 820px;
  max-width: 95vw;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
  overflow: hidden;
}
.preview-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 20px;
  border-bottom: 1px solid #e2e8f0;
  background: #f8fafc;
}
.preview-file-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.95rem;
  font-weight: 500;
  color: #1e293b;
}
.preview-icon { font-size: 1.1rem; }
.preview-close {
  width: 32px; height: 32px;
  border: none; background: none;
  font-size: 1.2rem; cursor: pointer;
  color: #94a3b8; border-radius: 6px;
  display: flex; align-items: center; justify-content: center;
}
.preview-close:hover { background: #e2e8f0; color: #1e293b; }
.preview-toolbar {
  display: flex; justify-content: space-between;
  padding: 8px 20px; border-bottom: 1px solid #e2e8f0;
  background: #f8fafc; font-size: 0.78rem; color: #94a3b8;
}
.preview-body { flex: 1; overflow-y: auto; padding: 0; min-height: 200px; }
.preview-loading {
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 12px; padding: 60px 0;
  color: #94a3b8; font-size: 0.9rem;
}
.preview-content {
  margin: 0; padding: 20px 24px;
  font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
  font-size: 0.82rem; line-height: 1.6; color: #334155;
  white-space: pre-wrap; word-wrap: break-word; tab-size: 2;
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}
.modal {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
  width: 520px;
  max-height: 90vh;
  overflow-y: auto;
}
.modal h3 {
  margin: 0 0 20px;
  color: #1e293b;
  font-size: 1.1rem;
}
.field {
  margin-bottom: 14px;
  flex: 1;
}
.field label {
  display: block;
  font-size: 0.85rem;
  color: #64748b;
  margin-bottom: 4px;
}
.field .required {
  color: #dc2626;
}
.field input, .field select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
  box-sizing: border-box;
}
.field input:focus, .field select:focus {
  border-color: #4f46e5;
}
.field input:disabled {
  background: #f1f5f9;
  color: #94a3b8;
  cursor: not-allowed;
}
.field-row {
  display: flex;
  gap: 14px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}
.btn-cancel {
  padding: 8px 20px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn-save {
  padding: 8px 20px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}
.btn-save:disabled {
  opacity: 0.6;
}
</style>