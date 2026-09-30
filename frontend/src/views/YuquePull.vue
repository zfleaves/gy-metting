<template>
  <div class="yuque-page">
    <div class="page-header">
      <h1>语雀拉取</h1>
      <p>选择语雀来源，输入需求号拉取关联文档</p>
    </div>

    <!-- 工具栏 -->
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input v-model="searchQuery" placeholder="搜索来源名称..." clearable style="max-width: 320px" @input="() => {}" />
      </div>
      <div class="toolbar-right">
        <el-button type="primary" @click="openAddModal">+ 新增来源</el-button>
      </div>
    </div>

    <!-- 来源表格 -->
    <el-table :data="filteredSources" stripe>
      <el-table-column type="index" :index="1" label="序号" width="70" />
      <el-table-column prop="name" label="名称" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.name }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="yuque_url" label="知识库 URL" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.yuque_url || '-' }}</template>
      </el-table-column>
      <el-table-column prop="token" label="Token" width="140">
        <template #default="{ row }">
          <el-tag size="small" type="info" effect="plain">{{ row.token }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="Session" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.has_session ? 'success' : 'info'" size="small" effect="plain">
            {{ row.has_session ? '有' : '无' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="CToken" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.has_ctoken ? 'success' : 'info'" size="small" effect="plain">
            {{ row.has_ctoken ? '有' : '无' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          <span class="time-cell">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEditModal(row)">修改</el-button>
          <el-button size="small" type="danger" @click="removeSource(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 拉取区 -->
    <div class="pull-section">
      <div class="pull-row">
        <el-select v-model="selectedSource" placeholder="-- 选择来源 --" style="min-width: 180px">
          <el-option v-for="s in sources" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-input
          v-model="requirementId"
          placeholder="输入需求号，如 SCPRO-1071 或 MOPRO-1900"
          :disabled="!selectedSource"
          clearable
          @keyup.enter="doPull"
        />
        <el-button type="primary" @click="doPull" :disabled="!selectedSource" :loading="pulling">
          {{ pulling ? '拉取中...' : '拉取需求' }}
        </el-button>
      </div>
      <div v-if="pullError" class="error-msg">{{ pullError }}</div>
    </div>

    <!-- 拉取结果 -->
    <el-card v-if="pullResult" shadow="never" class="result-card">
      <template #header>
        <div class="result-header">
          <span>拉取结果：{{ pullResult.matched_title }}</span>
          <el-tag size="small" type="info" effect="plain">共 {{ pullResult.total }} 个文档</el-tag>
        </div>
      </template>
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
    </el-card>

    <!-- 文档预览弹窗 -->
    <el-dialog v-model="previewVisible" :title="previewTitle" width="800px" @close="doClosePreview">
      <div v-if="previewLoading" class="preview-loading">
        <div class="spinner"></div>
        <span>加载文档内容...</span>
      </div>
      <pre v-else class="preview-content">{{ previewContent }}</pre>
      <div v-if="previewMeta" class="preview-meta-bar">
        {{ previewMeta.size }} 字 · {{ previewMeta.created_at }}
      </div>
    </el-dialog>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="showModal" :title="editingId ? '修改来源' : '新增来源'" width="560">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：冲鸭" />
        </el-form-item>
        <el-form-item label="知识库 URL">
          <el-input v-model="form.yuque_url" placeholder="语雀知识库 URL" />
        </el-form-item>
        <el-form-item label="Token" required>
          <el-input
            v-model="form.token"
            :placeholder="editingId ? '已配置（不可修改）' : '语雀 API Token'"
            :disabled="!!editingId"
          />
        </el-form-item>
        <div class="field-row">
          <el-form-item label="Session" style="flex: 1">
            <el-input
              v-model="form.session"
              :placeholder="editingId ? (editingSource?.has_session ? '已设置' : '未设置') : '可选'"
              :disabled="!!editingId"
            />
          </el-form-item>
          <el-form-item label="CToken" style="flex: 1">
            <el-input
              v-model="form.ctoken"
              :placeholder="editingId ? (editingSource?.has_ctoken ? '已设置' : '未设置') : '可选'"
              :disabled="!!editingId"
            />
          </el-form-item>
        </div>
        <el-form-item label="排除关键词">
          <el-input v-model="form.exclude" placeholder="逗号分隔，可选" />
        </el-form-item>
        <div class="field-row">
          <el-form-item label="附件类型" style="flex: 1">
            <el-input v-model="form.attachment_types" placeholder="可选" />
          </el-form-item>
          <el-form-item label="嵌入类型" style="flex: 1">
            <el-input v-model="form.embed_types" placeholder="可选" />
          </el-form-item>
        </div>
        <div v-if="modalError" class="error-msg">{{ modalError }}</div>
      </el-form>
      <template #footer>
        <el-button @click="closeModal">取消</el-button>
        <el-button type="primary" @click="saveSource" :loading="sourceSaving">保存</el-button>
      </template>
    </el-dialog>
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

const previewDocId = ref(null)
const previewTitle = ref('')
const previewContent = ref('')
const previewLoading = ref(false)
const previewMeta = ref(null)
const previewVisible = ref(false)

const showModal = ref(false)
const editingId = ref(null)
const editingSource = ref(null)
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
    token: s.token || '',
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
  previewVisible.value = true
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

function doClosePreview() {
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
.yuque-page { padding: 24px; }
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 12px; }
.toolbar-left { flex: 1; }
.time-cell { color: #94a3b8; white-space: nowrap; }

.pull-section { margin-bottom: 24px; margin-top: 16px; }
.pull-row { display: flex; gap: 8px; align-items: center; }
.error-msg { color: #dc2626; background: #fef2f2; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; margin-top: 8px; }

.result-header { display: flex; align-items: center; justify-content: space-between; }
.result-item { display: flex; align-items: center; gap: 10px; padding: 8px 0; font-size: 0.9rem; border-bottom: 1px solid #f1f5f9; }
.result-item:last-child { border-bottom: none; }
.result-item.failed { color: #dc2626; }
.result-icon { flex-shrink: 0; }
.result-title { flex: 1; }
.result-title.link { color: #4f46e5; cursor: pointer; }
.result-title.link:hover { text-decoration: underline; }
.result-error { font-size: 0.8rem; color: #94a3b8; }

.preview-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 60px 0; color: #94a3b8; font-size: 0.9rem; }
.spinner { width: 28px; height: 28px; border: 3px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.preview-content { margin: 0; padding: 0; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 0.82rem; line-height: 1.6; color: #334155; white-space: pre-wrap; word-wrap: break-word; }
.preview-meta-bar { font-size: 0.78rem; color: #94a3b8; padding: 8px 0; }

.field-row { display: flex; gap: 14px; }
</style>