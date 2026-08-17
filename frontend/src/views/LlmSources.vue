<template>
  <div class="llm-page">
    <div class="page-header">
      <h1>LLM 来源管理</h1>
      <p>管理多个 LLM 配置，切换当前使用的模型</p>
    </div>

    <div class="toolbar">
      <input v-model="searchQuery" class="search-input" placeholder="搜索名称..." />
      <button class="btn-add" @click="openAddModal">+ 新增来源</button>
    </div>

    <div class="table-wrap">
      <table class="llm-table">
        <thead>
          <tr>
            <th>#</th>
            <th>名称</th>
            <th>提供商</th>
            <th>模型</th>
            <th>API 地址</th>
            <th>API Key</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="9" class="empty-cell">加载中...</td></tr>
          <tr v-else-if="!filteredList.length"><td colspan="9" class="empty-cell">暂无 LLM 来源</td></tr>
          <tr v-for="(s, idx) in filteredList" :key="s.id">
            <td class="cell-idx">{{ idx + 1 }}</td>
            <td><strong>{{ s.name }}</strong></td>
            <td>{{ providerLabel(s.provider) }}</td>
            <td><code class="model-tag">{{ s.model }}</code></td>
            <td class="url-cell" :title="s.base_url">{{ s.base_url || '-' }}</td>
            <td><code class="key-tag">{{ s.api_key }}</code></td>
            <td>
              <span v-if="s.is_active" class="active-badge">✅ 当前</span>
              <button v-else class="btn-activate" @click="doActivate(s)">激活</button>
            </td>
            <td class="time-cell">{{ formatTime(s.created_at) }}</td>
            <td>
              <div class="action-btns">
                <button class="btn-edit" @click="openEditModal(s)">修改</button>
                <button class="btn-del" @click="doDelete(s)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增/编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay">
      <div class="modal">
        <h3>{{ editingId ? '修改来源' : '新增来源' }}</h3>

        <div class="field">
          <label>名称 <span class="required">*</span></label>
          <input v-model="form.name" type="text" placeholder="如：DeepSeek 主力" />
        </div>

        <div class="field-row">
          <div class="field">
            <label>提供商</label>
            <select v-model="form.provider" @change="onProviderChange">
              <option value="openai">OpenAI</option>
              <option value="deepseek">DeepSeek</option>
              <option value="qwen">通义千问 (Qwen)</option>
              <option value="glm">智谱 GLM</option>
              <option value="custom">自定义</option>
            </select>
          </div>
          <div class="field">
            <label>模型 <span class="required">*</span></label>
            <input v-model="form.model" type="text" :placeholder="modelPlaceholder" />
          </div>
        </div>

        <div class="field">
          <label>API 地址</label>
          <input v-model="form.base_url" type="text" :placeholder="baseUrlPlaceholder" />
        </div>

        <div class="field">
          <label>API Key <span class="required">*</span></label>
          <div class="password-wrap">
            <input
              v-model="form.api_key"
              :type="showKey ? 'text' : 'password'"
              :placeholder="editingId ? '留空则不修改' : 'sk-...'"
            />
            <button class="eye-btn" type="button" @click="showKey = !showKey">
              {{ showKey ? '🙈' : '👁️' }}
            </button>
          </div>
        </div>

        <div class="field-row">
          <div class="field">
            <label>Temperature</label>
            <input v-model="form.temperature" type="text" placeholder="0.3" />
          </div>
          <div class="field">
            <label>Max Tokens</label>
            <input v-model="form.max_tokens" type="text" placeholder="4096" />
          </div>
        </div>

        <div v-if="modalError" class="modal-error">{{ modalError }}</div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="closeModal">取消</button>
          <button class="btn-save" @click="saveSource" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listLlmSources, createLlmSource, updateLlmSource, deleteLlmSource, activateLlmSource } from '../api.js'

const sources = ref([])
const loading = ref(true)
const searchQuery = ref('')
const showModal = ref(false)
const editingId = ref(null)
const saving = ref(false)
const modalError = ref('')
const showKey = ref(false)
const form = ref({
  name: '', provider: 'openai', base_url: '', api_key: '',
  model: '', temperature: '0.3', max_tokens: '4096',
})

const filteredList = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return sources.value
  return sources.value.filter(s => s.name.toLowerCase().includes(q))
})

const PROVIDER_MAP = {
  openai: { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  deepseek: { label: 'DeepSeek', base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  qwen: { label: '通义千问', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  glm: { label: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-plus' },
  custom: { label: '自定义', base_url: '', model: '' },
}

const modelPlaceholder = computed(() => PROVIDER_MAP[form.value.provider]?.model || '模型名')
const baseUrlPlaceholder = computed(() => PROVIDER_MAP[form.value.provider]?.base_url || 'https://...')

function providerLabel(p) {
  return PROVIDER_MAP[p]?.label || p
}

function onProviderChange() {
  const p = PROVIDER_MAP[form.value.provider]
  if (p && form.value.provider !== 'custom') {
    if (!form.value.base_url) form.value.base_url = p.base_url
    if (!form.value.model) form.value.model = p.model
  }
}

onMounted(async () => {
  try { sources.value = await listLlmSources() } catch { /* ignore */ }
  finally { loading.value = false }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function openAddModal() {
  editingId.value = null
  form.value = { name: '', provider: 'openai', base_url: '', api_key: '', model: '', temperature: '0.3', max_tokens: '4096' }
  modalError.value = ''
  showModal.value = true
}

function openEditModal(s) {
  editingId.value = s.id
  form.value = {
    name: s.name,
    provider: s.provider,
    base_url: s.base_url || '',
    api_key: s.api_key || '', // 显示 masked key（如 "sk-VV7u2***"）
    model: s.model,
    temperature: s.temperature || '0.3',
    max_tokens: s.max_tokens || '4096',
  }
  modalError.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingId.value = null
}

async function saveSource() {
  modalError.value = ''
  if (!form.value.name.trim()) { modalError.value = '名称不能为空'; return }
  if (!editingId.value && !form.value.api_key.trim()) { modalError.value = 'API Key 不能为空'; return }
  if (!form.value.model.trim()) { modalError.value = '模型不能为空'; return }

  saving.value = true
  try {
    if (editingId.value) {
      // 编辑时只传有值的字段，api_key 为空时不覆盖
      const payload = { name: form.value.name, provider: form.value.provider, base_url: form.value.base_url, model: form.value.model, temperature: form.value.temperature, max_tokens: form.value.max_tokens }
      if (form.value.api_key.trim()) payload.api_key = form.value.api_key.trim()
      await updateLlmSource(editingId.value, payload)
    } else {
      await createLlmSource(form.value)
    }
    sources.value = await listLlmSources()
    closeModal()
  } catch (e) {
    modalError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function doActivate(s) {
  try {
    await activateLlmSource(s.id)
    sources.value = await listLlmSources()
  } catch (e) {
    alert('激活失败: ' + (e.message || '未知错误'))
  }
}

async function doDelete(s) {
  if (!confirm(`确定删除 LLM 来源「${s.name}」？`)) return
  try {
    await deleteLlmSource(s.id)
    sources.value = await listLlmSources()
  } catch (e) {
    alert('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.llm-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.search-input { flex: 1; max-width: 320px; padding: 8px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; }
.search-input:focus { border-color: #4f46e5; }
.btn-add { padding: 8px 18px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; white-space: nowrap; }
.btn-add:hover { background: #4338ca; }

.table-wrap { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.llm-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; table-layout: auto; }
.llm-table thead { background: #f8fafc; }
.llm-table th { text-align: left; padding: 10px 14px; font-weight: 600; color: #64748b; font-size: 0.82rem; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.llm-table td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; color: #334155; }
.llm-table tbody tr:hover { background: #f8fafc; }
.llm-table tbody tr:last-child td { border-bottom: none; }
.empty-cell { text-align: center; color: #94a3b8; padding: 40px 14px !important; }
.cell-idx { color: #94a3b8; width: 1%; white-space: nowrap; }
.url-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.time-cell { color: #94a3b8; white-space: nowrap; }
.model-tag { font-size: 0.8rem; background: #eef2ff; color: #4f46e5; padding: 2px 6px; border-radius: 3px; }
.key-tag { font-size: 0.78rem; color: #94a3b8; background: #f1f5f9; padding: 2px 6px; border-radius: 3px; }

.active-badge { font-size: 0.8rem; color: #16a34a; font-weight: 500; }
.btn-activate { padding: 3px 10px; border: 1px dashed #cbd5e1; background: none; border-radius: 4px; cursor: pointer; font-size: 0.78rem; color: #4f46e5; }
.btn-activate:hover { border-color: #4f46e5; background: #eef2ff; }

.action-btns { display: flex; gap: 6px; width: 1%; white-space: nowrap; }
.btn-edit { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #4f46e5; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-edit:hover { background: #eef2ff; }
.btn-del { padding: 4px 12px; border: 1px solid #fecaca; background: #fff; color: #dc2626; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-del:hover { background: #fef2f2; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: #fff; border-radius: 12px; padding: 28px; width: 560px; max-height: 90vh; overflow-y: auto; }
.modal h3 { margin: 0 0 20px; color: #1e293b; font-size: 1.1rem; }
.field { margin-bottom: 14px; flex: 1; }
.field label { display: block; font-size: 0.85rem; color: #64748b; margin-bottom: 4px; }
.field .required { color: #dc2626; }
.field input, .field select { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; }
.password-wrap { display: flex; align-items: center; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; }
.password-wrap input { border: none !important; flex: 1; }
.eye-btn { padding: 0 10px; border: none; background: none; cursor: pointer; font-size: 1rem; line-height: 1; }
.field input:focus, .field select:focus { border-color: #4f46e5; }
.field input:disabled { background: #f1f5f9; color: #94a3b8; cursor: not-allowed; }
.field-row { display: flex; gap: 14px; }
.bg-input { resize: vertical; font-family: inherit; }
.modal-error { color: #dc2626; font-size: 0.85rem; margin-bottom: 12px; padding: 8px; background: #fef2f2; border-radius: 6px; }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.btn-cancel { padding: 8px 20px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-save { padding: 8px 20px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
.btn-save:disabled { opacity: 0.6; }
</style>