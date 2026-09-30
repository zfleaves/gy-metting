<template>
  <div class="llm-page">
    <div class="page-header">
      <h1>LLM 来源管理</h1>
      <p>管理多个 LLM 配置，切换当前使用的模型</p>
    </div>

    <div class="toolbar">
      <el-input v-model="searchQuery" class="search-input" placeholder="搜索名称..." clearable @input="() => {}" />
      <el-button type="primary" @click="openAddModal">+ 新增来源</el-button>
    </div>

    <div v-if="loadError" class="load-error">{{ loadError }}</div>

    <el-table :data="filteredList" v-loading="loading" stripe>
      <el-table-column type="index" :index="1" label="#" width="60" />
      <el-table-column prop="name" label="名称" min-width="120">
        <template #default="{ row }">
          <strong>{{ row.name }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="provider" label="提供商" width="100">
        <template #default="{ row }">
          {{ providerLabel(row.provider) }}
        </template>
      </el-table-column>
      <el-table-column prop="model" label="模型" width="140">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.model }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="base_url" label="API 地址" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.base_url || '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="api_key" label="API Key" width="140">
        <template #default="{ row }">
          <el-tag size="small" type="info" effect="plain">{{ row.api_key }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.is_active" type="success" size="small" effect="dark">当前</el-tag>
          <el-button v-else size="small" @click="doActivate(row)">激活</el-button>
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
          <el-button size="small" type="danger" @click="doDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="showModal" :title="editingId ? '修改来源' : '新增来源'" width="580">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如：DeepSeek 主力" />
        </el-form-item>

        <div class="field-row">
          <el-form-item label="提供商" style="flex: 1">
            <el-select v-model="form.provider" style="width: 100%" @change="onProviderChange">
              <el-option label="OpenAI" value="openai" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="通义千问 (Qwen)" value="qwen" />
              <el-option label="智谱 GLM" value="glm" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型" required style="flex: 1">
            <el-input v-model="form.model" :placeholder="modelPlaceholder" />
          </el-form-item>
        </div>

        <el-form-item label="API 地址">
          <el-input v-model="form.base_url" :placeholder="baseUrlPlaceholder" />
        </el-form-item>

        <el-form-item label="API Key" required>
          <el-input
            v-model="form.api_key"
            :type="showKey ? 'text' : 'password'"
            :placeholder="editingId ? '留空则不修改' : 'sk-...'"
          >
            <template #suffix>
              <el-button link @click="showKey = !showKey">
                {{ showKey ? '🙈' : '👁️' }}
              </el-button>
            </template>
          </el-input>
        </el-form-item>

        <div class="field-row">
          <el-form-item label="Temperature" style="flex: 1">
            <el-input v-model="form.temperature" placeholder="0.3" />
          </el-form-item>
          <el-form-item label="Max Tokens" style="flex: 1">
            <el-input v-model="form.max_tokens" placeholder="4096" />
          </el-form-item>
        </div>

        <div v-if="modalError" class="modal-error">{{ modalError }}</div>
      </el-form>
      <template #footer>
        <el-button @click="closeModal">取消</el-button>
        <el-button type="primary" @click="saveSource" :loading="saving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listLlmSources, createLlmSource, updateLlmSource, deleteLlmSource, activateLlmSource } from '../api.js'
import { toast } from '../toast.js'

const sources = ref([])
const loading = ref(true)
const loadError = ref('')
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
  try { sources.value = await listLlmSources() }
  catch (e) { loadError.value = e.message || '加载失败，请检查登录状态' }
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
    api_key: s.api_key || '',
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
    toast.error('激活失败: ' + (e.message || '未知错误'))
  }
}

async function doDelete(s) {
  try {
    await ElMessageBox.confirm(`确定删除 LLM 来源「${s.name}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteLlmSource(s.id)
    sources.value = await listLlmSources()
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.llm-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.search-input { max-width: 320px; }

.time-cell { color: #94a3b8; font-size: 0.85rem; white-space: nowrap; }
.field-row { display: flex; gap: 14px; }
.load-error { color: #dc2626; background: #fef2f2; padding: 10px 16px; border-radius: 6px; font-size: 0.85rem; margin-bottom: 16px; }
.modal-error { color: #dc2626; font-size: 0.85rem; margin-bottom: 12px; padding: 8px; background: #fef2f2; border-radius: 6px; }
</style>