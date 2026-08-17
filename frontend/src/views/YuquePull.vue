<template>
  <div class="yuque-page">
    <div class="page-header">
      <h1>语雀拉取</h1>
      <p>选择语雀来源，输入需求号拉取关联文档</p>
    </div>

    <!-- 来源选择 -->
    <div class="source-row">
      <select v-model="selectedSource" class="source-select">
        <option value="">-- 选择来源 --</option>
        <option v-for="s in sources" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <button class="btn-manage" @click="showPanel = !showPanel">⚙️ 管理来源</button>
    </div>

    <!-- 来源管理面板 -->
    <div v-if="showPanel" class="source-panel">
      <div class="source-list">
        <div v-if="!sources.length" class="empty-hint">暂无来源</div>
        <div v-for="s in sources" :key="s.id" class="source-item">
          <div class="source-info">
            <strong>{{ s.name }}</strong>
            <span class="token-preview">{{ s.token }}</span>
            <span v-if="s.yuque_url" class="url-preview">{{ s.yuque_url }}</span>
          </div>
          <div class="source-actions">
            <button class="btn-sm" @click="editSource(s)">✎</button>
            <button class="btn-sm btn-del-sm" @click="removeSource(s)">🗑</button>
          </div>
        </div>
      </div>
      <div class="source-add">
        <input v-model="newSource.name" class="input-sm" placeholder="名称（如：冲鸭）" />
        <input v-model="newSource.yuque_url" class="input-sm input-full" placeholder="知识库 URL" />
        <input v-model="newSource.token" class="input-sm" placeholder="Token" />
        <input v-model="newSource.session" class="input-sm" placeholder="Session（可选）" />
        <input v-model="newSource.ctoken" class="input-sm" placeholder="CToken（可选）" />
        <input v-model="newSource.exclude" class="input-sm" placeholder="排除关键词，逗号分隔（可选）" />
        <input v-model="newSource.attachment_types" class="input-sm" placeholder="附件类型（可选）" />
        <input v-model="newSource.embed_types" class="input-sm" placeholder="嵌入类型（可选）" />
        <button class="btn-primary btn-sm" @click="saveSource" :disabled="sourceSaving">
          {{ editingId ? '更新' : '添加' }}
        </button>
        <button v-if="editingId" class="btn-cancel btn-sm" @click="cancelEdit">取消</button>
      </div>
    </div>

    <!-- 拉取区 -->
    <div class="pull-section">
      <div class="pull-row">
        <input
          v-model="requirementId"
          class="pull-input"
          placeholder="输入需求号，如 SCPRO-1071 或 MOPRO-1900"
          @keyup.enter="doPull"
          :disabled="!selectedSource"
        />
        <button class="btn-primary btn-pull" @click="doPull" :disabled="!selectedSource || pulling">
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
          <span class="result-title">{{ r.title }}</span>
          <span v-if="r.status === 'failed'" class="result-error">{{ r.error }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listYuqueSources, createYuqueSource, updateYuqueSource, deleteYuqueSource, pullYuqueRequirement } from '../api.js'

const sources = ref([])
const selectedSource = ref('')
const showPanel = ref(false)
const editingId = ref(null)
const sourceSaving = ref(false)
const newSource = ref({ name: '', yuque_url: '', token: '', session: '', ctoken: '', exclude: '', attachment_types: '', embed_types: '' })

const requirementId = ref('')
const pulling = ref(false)
const pullError = ref('')
const pullResult = ref(null)

onMounted(async () => {
  try { sources.value = await listYuqueSources() } catch { /* ignore */ }
})

async function saveSource() {
  if (!newSource.value.name || !newSource.value.token) return
  sourceSaving.value = true
  try {
    if (editingId.value) {
      await updateYuqueSource(editingId.value, newSource.value)
    } else {
      await createYuqueSource(newSource.value)
    }
    sources.value = await listYuqueSources()
    newSource.value = { name: '', yuque_url: '', token: '', session: '', ctoken: '', exclude: '', attachment_types: '', embed_types: '' }
    editingId.value = null
  } catch (e) {
    alert('保存失败: ' + (e.message || '未知错误'))
  } finally { sourceSaving.value = false }
}

function editSource(s) {
  editingId.value = s.id
  newSource.value = { name: s.name, yuque_url: s.yuque_url || '', token: '', session: '', ctoken: '', exclude: s.exclude || '', attachment_types: s.attachment_types || '', embed_types: s.embed_types || '' }
  showPanel.value = true
}

function cancelEdit() {
  editingId.value = null
  newSource.value = { name: '', yuque_url: '', token: '', session: '', ctoken: '', exclude: '', attachment_types: '', embed_types: '' }
}

async function removeSource(s) {
  if (!confirm(`确定删除来源「${s.name}」？`)) return
  try {
    await deleteYuqueSource(s.id)
    if (selectedSource.value === s.id) selectedSource.value = ''
    sources.value = await listYuqueSources()
  } catch (e) { alert('删除失败: ' + (e.message || '未知错误')) }
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
  } finally { pulling.value = false }
}
</script>

<style scoped>
.yuque-page { padding: 24px; max-width: 800px; }
.page-header { margin-bottom: 20px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

/* Source selector */
.source-row { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; }
.source-select { flex: 1; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.9rem; background: #fff; outline: none; }
.source-select:focus { border-color: #4f46e5; }
.btn-manage { padding: 10px 16px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fff; font-size: 0.85rem; cursor: pointer; color: #64748b; white-space: nowrap; }
.btn-manage:hover { border-color: #4f46e5; color: #4f46e5; }

/* Source panel */
.source-panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin-bottom: 20px; }
.source-list { margin-bottom: 12px; }
.source-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #f1f5f9; }
.source-info { display: flex; flex-direction: column; gap: 2px; }
.source-info strong { font-size: 0.85rem; color: #1e293b; }
.token-preview { font-size: 0.75rem; color: #94a3b8; font-family: monospace; }
.url-preview { font-size: 0.7rem; color: #94a3b8; word-break: break-all; }
.source-actions { display: flex; gap: 4px; }
.source-add { display: flex; flex-wrap: wrap; gap: 6px; }
.empty-hint { color: #94a3b8; font-size: 0.85rem; padding: 8px 0; }

.input-sm { padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.8rem; outline: none; flex: 1; min-width: 120px; }
.input-sm.input-full { flex: 1 1 100%; min-width: 100%; }
.input-sm:focus { border-color: #4f46e5; }

.btn-sm { padding: 6px 12px; border-radius: 4px; font-size: 0.8rem; border: 1px solid #e2e8f0; background: #fff; cursor: pointer; }
.btn-sm.btn-primary { background: #4f46e5; color: #fff; border: none; }
.btn-sm.btn-primary:disabled { opacity: 0.6; }
.btn-sm.btn-cancel { background: #f1f5f9; color: #64748b; }
.btn-del-sm { color: #dc2626; border-color: #fee2e2; }
.btn-del-sm:hover { background: #fef2f2; }

.btn-primary { padding: 10px 24px; background: #4f46e5; color: #fff; border-radius: 8px; font-size: 0.9rem; border: none; cursor: pointer; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.spinner-sm { width: 14px; height: 14px; border: 2px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; display: inline-block; margin-right: 6px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Pull section */
.pull-section { margin-bottom: 24px; }
.pull-row { display: flex; gap: 8px; }
.pull-input { flex: 1; padding: 12px 16px; border: 1px solid #e2e8f0; border-radius: 8px; font-size: 0.95rem; outline: none; }
.pull-input:focus { border-color: #4f46e5; }
.pull-input:disabled { background: #f8fafc; }
.btn-pull { padding: 12px 28px; font-size: 0.95rem; white-space: nowrap; }
.error-msg { color: #dc2626; background: #fef2f2; padding: 8px 12px; border-radius: 6px; font-size: 0.85rem; margin-top: 8px; }

/* Results */
.result-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.result-header { display: flex; align-items: center; justify-content: space-between; padding: 16px 20px; border-bottom: 1px solid #f1f5f9; }
.result-header h3 { margin: 0; font-size: 0.95rem; color: #1e293b; }
.result-count { font-size: 0.8rem; color: #94a3b8; }
.result-item { display: flex; align-items: center; gap: 10px; padding: 10px 20px; border-bottom: 1px solid #f1f5f9; font-size: 0.9rem; }
.result-item.ok { color: #334155; }
.result-item.failed { color: #dc2626; }
.result-icon { flex-shrink: 0; }
.result-title { flex: 1; }
.result-error { font-size: 0.8rem; color: #94a3b8; }
</style>