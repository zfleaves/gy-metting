<template>
  <div class="models-page">
    <div class="page-header">
      <h1>模型管理</h1>
      <p>管理 LLM 来源、Embedding 模型和 Reranker 模型</p>
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <!-- Tab 1: LLM 来源 -->
      <el-tab-pane label="LLM 来源" name="llm">
        <div class="toolbar">
          <el-input v-model="llmSearch" class="search-input" placeholder="搜索名称..." clearable @input="() => {}" />
          <el-button type="primary" @click="openLlmAdd">+ 新增来源</el-button>
        </div>
        <div v-if="llmLoadError" class="load-error">{{ llmLoadError }}</div>
        <el-table :data="llmFiltered" v-loading="llmLoading" stripe>
          <el-table-column type="index" :index="1" label="#" width="60" />
          <el-table-column prop="name" label="名称" min-width="120">
            <template #default="{ row }"><strong>{{ row.name }}</strong></template>
          </el-table-column>
          <el-table-column prop="provider" label="提供商" width="100">
            <template #default="{ row }">{{ providerLabel(row.provider) }}</template>
          </el-table-column>
          <el-table-column prop="model" label="模型" width="140">
            <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.model }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="base_url" label="API 地址" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.base_url || '-' }}</template>
          </el-table-column>
          <el-table-column prop="api_key" label="API Key" width="120">
            <template #default="{ row }"><el-tag size="small" type="info" effect="plain">{{ row.api_key }}</el-tag></template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" type="success" size="small" effect="dark">当前</el-tag>
              <el-button v-else size="small" @click="doLlmActivate(row)">激活</el-button>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }"><span class="time-cell">{{ formatTime(row.created_at) }}</span></template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openLlmEdit(row)">修改</el-button>
              <el-button size="small" @click="testConnection(row, 'llm')">测试</el-button>
              <el-button size="small" type="danger" @click="doLlmDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 2: Embedding 模型 -->
      <el-tab-pane label="Embedding 模型" name="embedding">
        <div class="toolbar">
          <span class="tab-desc">文本嵌入模型，用于语义检索参考文档</span>
          <el-button type="primary" @click="openRagAdd('embedding')">+ 添加模型</el-button>
        </div>
        <el-table :data="embeddingModels" v-loading="ragLoading" stripe>
          <el-table-column type="index" :index="1" label="#" width="60" />
          <el-table-column prop="name" label="名称" min-width="120">
            <template #default="{ row }"><strong>{{ row.name }}</strong></template>
          </el-table-column>
          <el-table-column prop="provider" label="提供商" width="100">
            <template #default="{ row }">{{ row.provider }}</template>
          </el-table-column>
          <el-table-column prop="model" label="模型" width="160">
            <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.model }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="api_key" label="API Key" width="120">
            <template #default="{ row }"><el-tag size="small" type="info" effect="plain">{{ row.api_key }}</el-tag></template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" type="success" size="small" effect="dark">当前</el-tag>
              <el-button v-else size="small" @click="doRagActivate(row)">激活</el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openRagEdit(row)">修改</el-button>
              <el-button size="small" @click="testConnection(row, 'rag')">测试</el-button>
              <el-button size="small" type="danger" @click="doRagDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 3: Reranker 模型 -->
      <el-tab-pane label="Reranker 模型" name="reranker">
        <div class="toolbar">
          <span class="tab-desc">重排序模型，对检索结果进行相关性重排</span>
          <el-button type="primary" @click="openRagAdd('reranker')">+ 添加模型</el-button>
        </div>
        <el-table :data="rerankerModels" v-loading="ragLoading" stripe>
          <el-table-column type="index" :index="1" label="#" width="60" />
          <el-table-column prop="name" label="名称" min-width="120">
            <template #default="{ row }"><strong>{{ row.name }}</strong></template>
          </el-table-column>
          <el-table-column prop="provider" label="提供商" width="100">
            <template #default="{ row }">{{ row.provider }}</template>
          </el-table-column>
          <el-table-column prop="model" label="模型" width="160">
            <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.model }}</el-tag></template>
          </el-table-column>
          <el-table-column prop="api_key" label="API Key" width="120">
            <template #default="{ row }"><el-tag size="small" type="info" effect="plain">{{ row.api_key }}</el-tag></template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag v-if="row.is_active" type="success" size="small" effect="dark">当前</el-tag>
              <el-button v-else size="small" @click="doRagActivate(row)">激活</el-button>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button size="small" @click="openRagEdit(row)">修改</el-button>
              <el-button size="small" @click="testConnection(row, 'rag')">测试</el-button>
              <el-button size="small" type="danger" @click="doRagDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- Tab 4: 工作流配置 -->
      <el-tab-pane label="工作流配置" name="workflow">
        <el-card class="workflow-card">
          <template #header>
            <span>多智能体工作流开关</span>
          </template>
          <el-form label-position="top">
            <el-form-item label="RAG 语义检索">
              <el-switch v-model="ragEnabled" active-text="启用" inactive-text="关闭" />
              <div class="form-help">启用后，生成纪要时自动使用激活的 Embedding 模型检索参考文档，再用 Reranker 重排序</div>
            </el-form-item>
            <el-form-item label="质量验证">
              <el-switch v-model="verifyEnabled" active-text="启用" inactive-text="关闭" />
              <div class="form-help">启用后，生成纪要后自动二次调用 LLM 检查幻觉、遗漏和格式</div>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card class="workflow-card">
          <template #header><span>当前模型链</span></template>
          <div class="model-chain">
            <div class="chain-step">
              <el-tag type="info">Embedding</el-tag>
              <span class="chain-val">{{ activeEmbedding || '未配置' }}</span>
            </div>
            <div class="chain-arrow">→</div>
            <div class="chain-step">
              <el-tag type="warning">Reranker</el-tag>
              <span class="chain-val">{{ activeReranker || '未配置' }}</span>
            </div>
            <div class="chain-arrow">→</div>
            <div class="chain-step">
              <el-tag type="success">LLM 生成</el-tag>
              <span class="chain-val">{{ activeLlm || '未配置' }}</span>
            </div>
          </div>
        </el-card>

        <el-card class="workflow-card">
          <template #header><span>保存配置</span></template>
          <el-button type="primary" @click="saveWorkflowConfig" :loading="savingConfig">保存工作流配置</el-button>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- LLM 来源新增/编辑弹窗 -->
    <el-dialog v-model="showLlmModal" :title="llmEditingId ? '修改来源' : '新增来源'" width="580">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="llmForm.name" placeholder="如：DeepSeek 主力" />
        </el-form-item>
        <div class="field-row">
          <el-form-item label="提供商" style="flex: 1">
            <el-select v-model="llmForm.provider" style="width: 100%" @change="onLlmProviderChange">
              <el-option label="OpenAI" value="openai" />
              <el-option label="DeepSeek" value="deepseek" />
              <el-option label="通义千问 (Qwen)" value="qwen" />
              <el-option label="智谱 GLM" value="glm" />
              <el-option label="Ollama" value="ollama" />
              <el-option label="自定义" value="custom" />
            </el-select>
          </el-form-item>
          <el-form-item label="模型" required style="flex: 1">
            <el-input v-model="llmForm.model" :placeholder="llmModelPlaceholder" />
          </el-form-item>
        </div>
        <el-form-item label="API 地址">
          <el-input v-model="llmForm.base_url" :placeholder="llmBaseUrlPlaceholder" />
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input v-model="llmForm.api_key" :type="showKey ? 'text' : 'password'" :placeholder="llmEditingId ? '留空则不修改' : 'sk-...'">
            <template #suffix>
              <el-button link @click="showKey = !showKey">{{ showKey ? '🙈' : '👁️' }}</el-button>
            </template>
          </el-input>
        </el-form-item>
        <div class="field-row">
          <el-form-item label="Temperature" style="flex: 1">
            <el-input v-model="llmForm.temperature" placeholder="0.3" />
          </el-form-item>
          <el-form-item label="Max Tokens" style="flex: 1">
            <el-input v-model="llmForm.max_tokens" placeholder="4096" />
          </el-form-item>
        </div>
        <div v-if="llmModalError" class="modal-error">{{ llmModalError }}</div>
      </el-form>
      <template #footer>
        <el-button @click="showLlmModal = false">取消</el-button>
        <el-button type="primary" @click="saveLlmSource" :loading="llmSaving">保存</el-button>
      </template>
    </el-dialog>

    <!-- RAG 模型新增/编辑弹窗 -->
    <el-dialog v-model="showRagModal" :title="ragEditingId ? '修改模型' : '添加模型'" width="520">
      <el-form label-position="top">
        <el-form-item label="名称" required>
          <el-input v-model="ragForm.name" :placeholder="ragType === 'embedding' ? '如：通义千问 Embedding' : '如：通义千问 Reranker'" />
        </el-form-item>
        <el-form-item label="提供商" style="flex: 1">
          <el-select v-model="ragForm.provider" style="width: 100%" @change="onRagProviderChange">
            <el-option label="自定义 (OpenAI 兼容)" value="custom" />
            <el-option label="DashScope (通义千问)" value="dashscope" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型" required>
          <el-input v-model="ragForm.model" :placeholder="ragType === 'embedding' ? 'text-embedding-v4' : 'qwen3-rerank'" />
        </el-form-item>
        <el-form-item label="API 地址">
          <el-input v-model="ragForm.base_url" :placeholder="ragBaseUrlPlaceholder" />
        </el-form-item>
        <el-form-item label="API Key" required>
          <el-input v-model="ragForm.api_key" type="password" :placeholder="ragEditingId ? '留空则不修改' : 'sk-...'" />
        </el-form-item>
        <div v-if="ragModalError" class="modal-error">{{ ragModalError }}</div>
      </el-form>
      <template #footer>
        <el-button @click="showRagModal = false">取消</el-button>
        <el-button type="primary" @click="saveRagModel" :loading="ragSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  listLlmSources, createLlmSource, updateLlmSource, deleteLlmSource, activateLlmSource,
  listRagModels, createRagModel, updateRagModel, deleteRagModel, activateRagModel, testRagModel,
} from '../api.js'
import { toast } from '../toast.js'

// ============================================================
// State
// ============================================================
const activeTab = ref('llm')

// --- LLM Sources ---
const llmSources = ref([])
const llmLoading = ref(true)
const llmLoadError = ref('')
const llmSearch = ref('')
const showLlmModal = ref(false)
const llmEditingId = ref(null)
const llmSaving = ref(false)
const llmModalError = ref('')
const showKey = ref(false)
const llmForm = ref({ name: '', provider: 'openai', base_url: '', api_key: '', model: '', temperature: '0.3', max_tokens: '4096' })

const PROVIDER_MAP = {
  openai: { label: 'OpenAI', base_url: 'https://api.openai.com/v1', model: 'gpt-4o' },
  deepseek: { label: 'DeepSeek', base_url: 'https://api.deepseek.com', model: 'deepseek-chat' },
  qwen: { label: '通义千问', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1', model: 'qwen-plus' },
  glm: { label: '智谱 GLM', base_url: 'https://open.bigmodel.cn/api/paas/v4', model: 'glm-4-plus' },
  ollama: { label: 'Ollama', base_url: 'http://localhost:11434/v1', model: 'llama3.1' },
  custom: { label: '自定义', base_url: '', model: '' },
}

const llmModelPlaceholder = computed(() => PROVIDER_MAP[llmForm.value.provider]?.model || '模型名')
const llmBaseUrlPlaceholder = computed(() => PROVIDER_MAP[llmForm.value.provider]?.base_url || 'https://...')

function providerLabel(p) { return PROVIDER_MAP[p]?.label || p }
function onLlmProviderChange() {
  const p = PROVIDER_MAP[llmForm.value.provider]
  if (p && llmForm.value.provider !== 'custom') {
    if (!llmForm.value.base_url) llmForm.value.base_url = p.base_url
    if (!llmForm.value.model) llmForm.value.model = p.model
  }
}

const llmFiltered = computed(() => {
  const q = llmSearch.value.trim().toLowerCase()
  if (!q) return llmSources.value
  return llmSources.value.filter(s => s.name.toLowerCase().includes(q))
})

// --- RAG Models ---
const ragModels = ref([])
const ragLoading = ref(false)
const showRagModal = ref(false)
const ragEditingId = ref(null)
const ragSaving = ref(false)

const RAG_PROVIDER_MAP = {
  dashscope: { label: 'DashScope', base_url: 'https://dashscope.aliyuncs.com/api/v1' },
  custom: { label: '自定义', base_url: '' },
}
const ragBaseUrlPlaceholder = computed(() => RAG_PROVIDER_MAP[ragForm.value.provider]?.base_url || 'https://...')

function onRagProviderChange() {
  const p = RAG_PROVIDER_MAP[ragForm.value.provider]
  if (p && ragForm.value.provider !== 'custom') {
    if (!ragForm.value.base_url) ragForm.value.base_url = p.base_url
  }
}
const ragModalError = ref('')
const ragType = ref('embedding') // 'embedding' or 'reranker'
const ragForm = ref({ name: '', provider: 'custom', base_url: '', api_key: '', model: '' })

const embeddingModels = computed(() => ragModels.value.filter(m => m.model_type === 'embedding'))
const rerankerModels = computed(() => ragModels.value.filter(m => m.model_type === 'reranker'))

// --- Workflow ---
const ragEnabled = ref(false)
const verifyEnabled = ref(false)
const savingConfig = ref(false)
const activeEmbedding = computed(() => {
  const a = embeddingModels.value.find(m => m.is_active)
  return a ? `${a.model} (${a.name})` : null
})
const activeReranker = computed(() => {
  const a = rerankerModels.value.find(m => m.is_active)
  return a ? `${a.model} (${a.name})` : null
})
const activeLlm = computed(() => {
  const a = llmSources.value.find(m => m.is_active)
  return a ? `${a.model} (${a.name})` : null
})

// ============================================================
// Lifecycle
// ============================================================
onMounted(() => {
  loadLlmSources()
  loadRagModels()
  loadWorkflowConfig()
})

function onTabChange(tab) {
  if (tab === 'llm') loadLlmSources()
  else if (tab === 'embedding' || tab === 'reranker') loadRagModels()
}

// ============================================================
// LLM Sources CRUD
// ============================================================
async function loadLlmSources() {
  llmLoading.value = true
  llmLoadError.value = ''
  try { llmSources.value = await listLlmSources() }
  catch (e) { llmLoadError.value = e.message || '加载失败' }
  finally { llmLoading.value = false }
}

function openLlmAdd() {
  llmEditingId.value = null
  llmForm.value = { name: '', provider: 'openai', base_url: '', api_key: '', model: '', temperature: '0.3', max_tokens: '4096' }
  llmModalError.value = ''
  showLlmModal.value = true
}

function openLlmEdit(s) {
  llmEditingId.value = s.id
  llmForm.value = {
    name: s.name, provider: s.provider, base_url: s.base_url || '', api_key: s.api_key || '',
    model: s.model, temperature: s.temperature || '0.3', max_tokens: s.max_tokens || '4096',
  }
  llmModalError.value = ''
  showLlmModal.value = true
}

async function saveLlmSource() {
  llmModalError.value = ''
  if (!llmForm.value.name.trim()) { llmModalError.value = '名称不能为空'; return }
  if (!llmEditingId.value && !llmForm.value.api_key.trim()) { llmModalError.value = 'API Key 不能为空'; return }
  if (!llmForm.value.model.trim()) { llmModalError.value = '模型不能为空'; return }
  llmSaving.value = true
  try {
    if (llmEditingId.value) {
      const payload = { name: llmForm.value.name, provider: llmForm.value.provider, base_url: llmForm.value.base_url, model: llmForm.value.model, temperature: llmForm.value.temperature, max_tokens: llmForm.value.max_tokens }
      if (llmForm.value.api_key.trim()) payload.api_key = llmForm.value.api_key.trim()
      await updateLlmSource(llmEditingId.value, payload)
    } else {
      await createLlmSource(llmForm.value)
    }
    await loadLlmSources()
    showLlmModal.value = false
  } catch (e) { llmModalError.value = e.message || '保存失败' }
  finally { llmSaving.value = false }
}

async function doLlmActivate(s) {
  try {
    await activateLlmSource(s.id)
    await loadLlmSources()
  } catch (e) { toast.error('激活失败: ' + (e.message || '未知错误')) }
}

async function doLlmDelete(s) {
  try {
    await ElMessageBox.confirm(`确定删除 LLM 来源「${s.name}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteLlmSource(s.id)
    await loadLlmSources()
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}

// ============================================================
// RAG Models CRUD
// ============================================================
async function loadRagModels() {
  ragLoading.value = true
  try { ragModels.value = await listRagModels() }
  catch (e) { toast.error('加载 RAG 模型失败: ' + (e.message || '未知错误')) }
  finally { ragLoading.value = false }
}

function openRagAdd(type) {
  ragType.value = type
  ragEditingId.value = null
  ragForm.value = { name: '', provider: 'custom', base_url: '', api_key: '', model: type === 'embedding' ? 'text-embedding-v4' : 'qwen3-rerank' }
  ragModalError.value = ''
  showRagModal.value = true
}

function openRagEdit(m) {
  ragType.value = m.model_type
  ragEditingId.value = m.id
  ragForm.value = { name: m.name, provider: m.provider, base_url: m.base_url, api_key: m.api_key, model: m.model }
  ragModalError.value = ''
  showRagModal.value = true
}

async function saveRagModel() {
  ragModalError.value = ''
  if (!ragForm.value.name.trim()) { ragModalError.value = '名称不能为空'; return }
  if (!ragEditingId.value && !ragForm.value.api_key.trim()) { ragModalError.value = 'API Key 不能为空'; return }
  if (!ragForm.value.model.trim()) { ragModalError.value = '模型不能为空'; return }
  ragSaving.value = true
  try {
    const data = {
      name: ragForm.value.name.trim(),
      model_type: ragType.value,
      provider: ragForm.value.provider,
      base_url: ragForm.value.base_url.trim(),
      api_key: ragForm.value.api_key.trim(),
      model: ragForm.value.model.trim(),
    }
    if (ragEditingId.value) {
      await updateRagModel(ragEditingId.value, data)
    } else {
      await createRagModel(data)
    }
    await loadRagModels()
    showRagModal.value = false
  } catch (e) { ragModalError.value = e.message || '保存失败' }
  finally { ragSaving.value = false }
}

async function doRagActivate(m) {
  try {
    await activateRagModel(m.id)
    await loadRagModels()
  } catch (e) { toast.error('激活失败: ' + (e.message || '未知错误')) }
}

async function doRagDelete(m) {
  try {
    await ElMessageBox.confirm(`确定删除 RAG 模型「${m.name}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteRagModel(m.id)
    await loadRagModels()
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}

// ============================================================
// Connection Test
// ============================================================
async function testConnection(item, type) {
  try {
    if (type === 'llm') {
      // LLM 连接测试：简单调用
      const msg = await ElMessageBox.prompt('输入测试消息（可选）', '测试连接', { inputValue: 'Hello', inputPlaceholder: '输入测试消息' })
      toast.info('测试中...')
      // 调用 LLM API 测试
      try {
        const token = localStorage.getItem('auth_token')
        const res = await fetch(`/api/llm-sources/${item.id}/test`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: msg.value }),
        })
        const data = await res.json()
        if (data.success) toast.success('✅ 连接成功')
        else toast.error('❌ 连接失败: ' + (data.message || '未知错误'))
      } catch (e) {
        toast.error('❌ 连接失败: ' + (e.message || '请求异常'))
      }
    } else {
      // RAG 模型测试
      toast.info('测试连接中...')
      const res = await testRagModel(item.id)
      if (res.success) toast.success('✅ 连接成功')
      else toast.error('❌ ' + (res.message || '连接失败'))
    }
  } catch (e) {
    // 用户取消输入
  }
}

// ============================================================
// Workflow Config (localStorage)
// ============================================================
function loadWorkflowConfig() {
  try {
    const cfg = JSON.parse(localStorage.getItem('workflow_config') || '{}')
    ragEnabled.value = cfg.rag_enabled ?? false
    verifyEnabled.value = cfg.verify_enabled ?? false
  } catch { /* ignore */ }
}

async function saveWorkflowConfig() {
  savingConfig.value = true
  try {
    localStorage.setItem('workflow_config', JSON.stringify({
      rag_enabled: ragEnabled.value,
      verify_enabled: verifyEnabled.value,
    }))
    toast.success('✅ 工作流配置已保存')
  } catch (e) {
    toast.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    savingConfig.value = false
  }
}

// ============================================================
// Utilities
// ============================================================
function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}
</script>

<style scoped>
.models-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }
.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.search-input { max-width: 320px; }
.tab-desc { color: #94a3b8; font-size: 0.85rem; }
.time-cell { color: #94a3b8; font-size: 0.85rem; white-space: nowrap; }
.field-row { display: flex; gap: 14px; }
.load-error { color: #dc2626; background: #fef2f2; padding: 10px 16px; border-radius: 6px; font-size: 0.85rem; margin-bottom: 16px; }
.modal-error { color: #dc2626; font-size: 0.85rem; margin-bottom: 12px; padding: 8px; background: #fef2f2; border-radius: 6px; }
.workflow-card { margin-bottom: 16px; }
.workflow-card .form-help { color: #94a3b8; font-size: 0.8rem; margin-top: 4px; }
.model-chain { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.chain-step { display: flex; align-items: center; gap: 8px; }
.chain-val { font-size: 0.9rem; color: #475569; }
.chain-arrow { color: #94a3b8; font-size: 1.2rem; }
@media (max-width: 768px) {
  .model-chain { flex-direction: column; align-items: flex-start; }
  .chain-arrow { transform: rotate(90deg); }
}
</style>