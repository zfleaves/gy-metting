<template>
  <div class="minutes-page">
    <div class="page-header">
      <h1>AI 纪要生成</h1>
      <p>选择已完成转写的任务，自动关联会议背景和参考文档，流式生成 AI 纪要</p>
    </div>

    <!-- 表单区 -->
    <div class="form-section">
      <div class="field">
        <label>选择转写任务 <span class="required">*</span></label>
        <select v-model="taskId" class="form-select">
          <option value="">-- 请选择已完成转写的任务 --</option>
          <option v-for="t in tasks" :key="t.id" :value="t.id">
            {{ t.name || t.id.slice(0, 8) }}
            <template v-if="t.meeting_id && meetingMap[t.meeting_id]">
              — {{ meetingMap[t.meeting_id] }}
            </template>
            （{{ formatTime(t.created_at) }}）
          </option>
        </select>
        <div v-if="taskId && selectedMeeting" class="selected-meeting">
          📋 关联会议：
          <a :href="`/meeting/${selectedMeeting.id}`" target="_blank" class="meeting-link">{{ selectedMeeting.title }}</a>
          <span class="doc-badge">{{ selectedMeeting.snapshot_ids?.length || 0 }} 个文档</span>
        </div>
        <div v-else-if="taskId" class="selected-meeting muted">
          📋 未关联会议，仅使用转写文本生成纪要
        </div>
        <div v-if="taskId && selectedTask" class="selected-task">
          🎙️ 转写任务：
          <a :href="`/task/${taskId}`" target="_blank" class="meeting-link">{{ selectedTask.name || taskId.slice(0, 8) }}</a>
          <span class="doc-badge">查看详情 →</span>
        </div>
      </div>

      <div class="field">
        <label>会议模板</label>
        <div class="template-tabs">
          <button
            v-for="t in templates"
            :key="t"
            class="template-tab"
            :class="{ active: meetingType === t }"
            :title="templateDesc[t]"
            @click="meetingType = t"
          >{{ t }}</button>
        </div>
        <div class="template-hint">
          {{ templateDesc[meetingType] }}
          <button class="btn-view-prompt" @click="showPrompt = true">查看提示词</button>
        </div>
      </div>

      <div class="field">
        <label>使用偏好（可选）</label>
        <select v-model="selectedPrefId" class="form-select">
          <option value="">-- 不使用偏好 --</option>
          <option v-for="p in adoptedPrefs" :key="p.id" :value="p.id">
            {{ p.name || p.meeting_type }} {{ p.is_default ? '⭐' : '' }}
          </option>
        </select>
        <div v-if="selectedPrefId && selectedPref" class="pref-hint">
          📎 {{ selectedPref.name }}（{{ selectedPref.meeting_type }}）
          <span v-if="selectedPref.notes">— {{ selectedPref.notes }}</span>
        </div>
      </div>

      <div class="field">
        <label>自定义提示词（可选，覆盖模板）</label>
        <textarea v-model="customPrompt" class="form-textarea" placeholder="留空则使用模板默认提示词..." rows="3"></textarea>
      </div>

      <div class="field-row">
        <div class="field">
          <label>
            Temperature
            <span class="tip-icon" data-tip="控制输出随机性：0=严格确定，2=高度随机。纪要生成推荐 0.1-0.5">?</span>
          </label>
          <input v-model.number="temperature" type="number" step="0.1" min="0" max="2" class="form-input" />
        </div>
        <div class="field">
          <label>
            Max Tokens
            <span class="tip-icon" data-tip="单次生成最大 Token 数，超出后内容截断。纪要建议 4096-8192">?</span>
          </label>
          <input v-model.number="maxTokens" type="number" step="1024" min="256" class="form-input" />
        </div>
      </div>

      <div class="form-actions">
        <button class="btn-generate" @click="startGenerate" :disabled="!taskId || generating">
          {{ generating ? '生成中...' : '🚀 生成纪要' }}
        </button>
        <button v-if="generating" class="btn-stop" @click="stopGenerate">停止</button>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="resultText || generating" class="result-section">
      <div class="result-header">
        <h3>生成结果</h3>
        <div class="result-actions">
          <button v-if="resultText && !generating && !editing" class="btn-edit" @click="startEdit">✏️ 编辑</button>
          <button v-if="done && !editing" class="btn-regen" @click="showRegenDialog = true">🔄 重新生成</button>
          <button v-if="editing" class="btn-save" @click="doSave" :disabled="saving">{{ saving ? '保存中...' : '💾 保存修改' }}</button>
          <button v-if="editing" class="btn-cancel-edit" @click="cancelEdit">取消</button>
          <button v-if="resultText" class="btn-copy" @click="copyResult">📋 复制</button>
          <span v-if="usage" class="usage-info">Token: {{ usage }}</span>
          <router-link v-if="done" to="/minutes" class="btn-view-list">📋 查看列表</router-link>
          <button v-if="done && !editing" class="btn-generate-sm" @click="resetForm">🔄 继续生成</button>
        </div>
      </div>
      <div class="result-body" ref="resultBody">
        <div v-if="!resultText && generating" class="generating-status">
          <div class="spinner"></div>
          <span>正在生成纪要，请稍候...</span>
        </div>
        <div v-if="editing" class="edit-area">
          <textarea v-model="editText" class="edit-textarea" @input="onEditInput"></textarea>
          <div class="edit-hint">支持 Markdown 格式，修改后点击「保存修改」</div>
        </div>
        <div v-else class="markdown-content" v-html="renderedResult"></div>
        <div v-if="generating && resultText" class="cursor-blink">▍</div>
        <div v-if="done && !editing" class="done-banner">✅ 纪要生成完成</div>
      </div>
    </div>

    <!-- 重新生成弹窗 -->
    <div v-if="showRegenDialog" class="modal-overlay" @click.self="showRegenDialog = false">
      <div class="regen-modal">
        <div class="modal-header">
          <h3>🔄 重新生成纪要</h3>
          <button class="modal-close" @click="showRegenDialog = false">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>修改原因 <span class="required">*</span></label>
            <select v-model="regenReason" class="form-select">
              <option value="">-- 请选择 --</option>
              <option value="内容不准确">内容不准确</option>
              <option value="遗漏关键信息">遗漏关键信息</option>
              <option value="格式不符合要求">格式不符合要求</option>
              <option value="决策描述不清晰">决策描述不清晰</option>
              <option value="其他">其他</option>
            </select>
          </div>
          <div class="field">
            <label>注意事项</label>
            <textarea v-model="regenNotes" class="form-textarea" rows="4" placeholder="输入你的具体要求，如：请重点关注待办事项的截止时间、把决策描述得更详细等"></textarea>
          </div>
          <div class="field">
            <label>使用偏好</label>
            <select v-model="regenPrefId" class="form-select">
              <option value="">-- 不使用偏好 --</option>
              <option v-for="p in adoptedPrefs" :key="p.id" :value="p.id">
                {{ p.name || p.meeting_type }} {{ p.is_default ? '⭐' : '' }}
              </option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="showRegenDialog = false">取消</button>
          <button class="btn-generate" @click="doRegenerate" :disabled="!regenReason || regenerating">
            {{ regenerating ? '重新生成中...' : '🚀 重新生成' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 提示词预览弹窗 -->
    <div v-if="showPrompt" class="modal-overlay" @click.self="showPrompt = false">
      <div class="prompt-modal">
        <div class="prompt-header">
          <h3>提示词模板：{{ meetingType }}</h3>
          <div class="prompt-header-actions">
            <button class="btn-copy-prompt" @click="copyPrompt">📋 复制</button>
            <button class="prompt-close" @click="showPrompt = false">✕</button>
          </div>
        </div>
        <div class="prompt-hint">以下是 AI 使用的系统提示词。你可以参考此格式，在「自定义提示词」中覆盖修改。</div>
        <pre class="prompt-body">{{ templatePrompts[meetingType] }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { listTasks, listMeetings, updateMinutes, listPreferences } from '../api.js'
import { marked } from 'marked'
import { toast } from '../toast.js'

marked.setOptions({ breaks: true, gfm: true })

const tasks = ref([])
const meetings = ref([])
const meetingMap = ref({})
const taskId = ref('')
const meetingType = ref('通用')
const customPrompt = ref('')
const temperature = ref(0.3)
const maxTokens = ref(8192)
const templates = ['通用', '需求评审', '技术评审', '周会']
const templateDesc = {
  '通用': '通用结构化输出：会议摘要、关键决策、待办事项、风险问题',
  '需求评审': '需求评审专用：评审结论、关键决策、待办事项、风险问题、变更记录（对照 PRD）',
  '技术评审': '技术评审专用：技术方案结论、关键决策、技术风险、架构变更',
  '周会': '周会/例会专用：上周进展、本周计划、风险阻塞、待办事项',
}
const templatePrompts = {
  '通用': `你是一个专业的会议纪要助手，负责将会议转写文本整理为结构化的会议纪要。

## 核心约束（必须遵守）
1. 全部决策、变更、待办、风险，必须来自会议转写文本，不得编造；
2. 参考文档仅作为业务基线，文档有但会上未讨论的内容，严禁输出评审结论；
3. 会议口头讨论优先级高于参考文档，发生冲突时以会议为准并标注变更；
4. 识别不到责任人或时间，统一标记【未指定责任人】【时间待确认】，禁止自行编造；
5. 过滤闲聊、跑题内容，只保留有效业务信息。

## 输出格式（Markdown）

### 会议基本信息
- **会议主题**：{meeting_title}
- **会议类型**：通用
- **业务背景**：{background}

### 会议摘要
（简要概括本次会议的核心内容）

### 关键决策
| 决策项 | 决策内容 | 决策人 |
|--------|---------|--------|

### 待办事项
| 待办项 | 责任人 | 截止时间 | 备注 |
|--------|--------|---------|------|

### 风险与问题
| 风险/问题 | 影响 | 建议方案 |
|----------|------|---------|

### 会议参与人
（根据会议讨论中提到的参与人整理）`,

  '需求评审': `你是一个专业的会议纪要助手，负责将会议转写文本整理为结构化的需求评审纪要。

## 核心约束（必须遵守）
1. 全部决策、变更、待办、风险，必须来自会议转写文本，不得编造；
2. 参考文档仅作为业务基线，文档有但会上未讨论的内容，严禁输出评审结论；
3. 会议口头讨论优先级高于参考文档，发生冲突时以会议为准并标注变更；
4. 识别不到责任人或时间，统一标记【未指定责任人】【时间待确认】，禁止自行编造；
5. 过滤闲聊、跑题内容，只保留有效业务信息。

## 输出格式（Markdown）

### 会议基本信息
- **会议主题**：{meeting_title}
- **会议类型**：需求评审
- **业务背景**：{background}

### 评审结论
（输出本次需求评审的最终结论：通过/不通过/有条件通过）

### 关键决策
| 决策项 | 决策内容 | 决策人 |
|--------|---------|--------|

### 待办事项
| 待办项 | 责任人 | 截止时间 | 备注 |
|--------|--------|---------|------|

### 风险与问题
| 风险/问题 | 影响 | 建议方案 |
|----------|------|---------|

### 变更记录
（与参考文档不一致的变更点，以会议口头讨论为准）

### 会议参与人
（根据会议讨论中提到的参与人整理）`,

  '技术评审': `你是一个专业的会议纪要助手，负责将技术评审会议转写文本整理为结构化的技术评审纪要。

## 核心约束（必须遵守）
1. 全部决策、变更、待办、风险，必须来自会议转写文本，不得编造；
2. 参考文档仅作为业务基线，文档有但会上未讨论的内容，严禁输出评审结论；
3. 会议口头讨论优先级高于参考文档，发生冲突时以会议为准并标注变更；
4. 识别不到责任人或时间，统一标记【未指定责任人】【时间待确认】，禁止自行编造；
5. 过滤闲聊、跑题内容，只保留有效业务信息。

## 输出格式（Markdown）

### 会议基本信息
- **会议主题**：{meeting_title}
- **会议类型**：技术评审
- **业务背景**：{background}

### 技术方案评审结论
（输出技术方案的评审结论：通过/不通过/修改后通过）

### 关键决策
| 决策项 | 决策内容 | 决策人 |
|--------|---------|--------|

### 待办事项
| 待办项 | 责任人 | 截止时间 | 备注 |
|--------|--------|---------|------|

### 技术风险
| 风险项 | 影响范围 | 应对方案 |
|--------|---------|---------|

### 架构变更
（涉及架构调整的变更点）

### 会议参与人
（根据会议讨论中提到的参与人整理）`,

  '周会': `你是一个专业的会议纪要助手，负责将周会/例会转写文本整理为结构化的会议纪要。

## 核心约束（必须遵守）
1. 全部决策、变更、待办、风险，必须来自会议转写文本，不得编造；
2. 过滤闲聊、跑题内容，只保留有效业务信息；
3. 识别不到责任人或时间，统一标记【未指定责任人】【时间待确认】，禁止自行编造。

## 输出格式（Markdown）

### 会议基本信息
- **会议主题**：{meeting_title}
- **会议类型**：周会
- **业务背景**：{background}

### 上周进展
（各成员/项目进展同步）

### 本周计划
（本周重点工作安排）

### 风险与阻塞
| 风险/阻塞项 | 责任人 | 需要支持 |
|------------|--------|---------|

### 待办事项
| 待办项 | 责任人 | 截止时间 |
|--------|--------|---------|`,
}
const showPrompt = ref(false)

const generating = ref(false)
const done = ref(false)
const router = useRouter()
const route = useRoute()
const resultText = ref('')
const usage = ref(null)
const abortController = ref(null)
const resultBody = ref(null)
const pendingBuffer = ref('')
let typingTimer = null
// 编辑相关
const recordId = ref(null)
const editing = ref(false)
const editText = ref('')
const saving = ref(false)
// 偏好相关
const adoptedPrefs = ref([])
const selectedPrefId = ref('')
// 重新生成弹窗
const showRegenDialog = ref(false)
const regenReason = ref('')
const regenNotes = ref('')
const regenPrefId = ref('')
const regenerating = ref(false)

const selectedMeeting = computed(() => {
  const t = tasks.value.find(t => t.id === taskId.value)
  if (!t || !t.meeting_id) return null
  return meetings.value.find(m => m.id === t.meeting_id) || null
})

const selectedTask = computed(() => {
  return tasks.value.find(t => t.id === taskId.value) || null
})

const selectedPref = computed(() => {
  if (!selectedPrefId.value) return null
  return adoptedPrefs.value.find(p => p.id === selectedPrefId.value) || null
})

const renderedResult = computed(() => {
  if (!resultText.value) return ''
  try {
    let html = marked.parse(resultText.value)
    html = html.replace(/<img src="https:\/\/cdn\.nlark\.com([^"]+)"/g, (match, path) => {
      const origUrl = `https://cdn.nlark.com${path}`
      return `<img src="/api/yuque-image-proxy?url=${encodeURIComponent(origUrl)}"`
    })
    return html
  } catch {
    return resultText.value
  }
})

onMounted(async () => {
  try {
    tasks.value = await listTasks({ task_type: 'asr', limit: 50 })
    // 如果 URL 带了 task_id 参数，自动选中
    const urlTaskId = route.query.task_id
    if (urlTaskId && tasks.value.some(t => t.id === urlTaskId)) {
      taskId.value = urlTaskId
    }
  } catch { /* ignore */ }
  try {
    meetings.value = await listMeetings()
    const map = {}
    for (const m of meetings.value) map[m.id] = m.title
    meetingMap.value = map
  } catch { /* ignore */ }
  // 加载已采纳偏好
  try {
    const res = await listPreferences({ adopted: 1 })
    adoptedPrefs.value = (res.preferences || [])
    // 如果有默认偏好，自动选中
    const defaultPref = adoptedPrefs.value.find(p => p.is_default)
    if (defaultPref) selectedPrefId.value = defaultPref.id
  } catch { /* ignore */ }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

watch(resultText, () => {
  nextTick(() => {
    if (resultBody.value) {
      resultBody.value.scrollTop = resultBody.value.scrollHeight
    }
  })
})

async function startGenerate(regenOpts) {
  if (!taskId.value) return
  generating.value = true
  done.value = false
  resultText.value = ''
  usage.value = null
  pendingBuffer.value = ''
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }

  const params = new URLSearchParams({ task_id: taskId.value })
  if (meetingType.value) params.set('meeting_type', meetingType.value)
  if (customPrompt.value.trim()) params.set('custom_prompt', customPrompt.value.trim())
  params.set('temperature', String(temperature.value))
  params.set('max_tokens', String(maxTokens.value))

  // 偏好与重新生成参数
  const prefId = regenOpts?.prefId || selectedPrefId.value
  if (prefId) params.set('preference_id', prefId)
  if (regenOpts?.reason) params.set('regenerate_reason', regenOpts.reason)
  if (regenOpts?.notes) params.set('regenerate_notes', regenOpts.notes)

  abortController.value = new AbortController()
  const token = localStorage.getItem('auth_token')

  // 打字机效果：每 35ms 从 pendingBuffer 取出一个字符显示
  typingTimer = setInterval(() => {
    if (pendingBuffer.value.length > 0) {
      resultText.value += pendingBuffer.value[0]
      pendingBuffer.value = pendingBuffer.value.slice(1)
    }
  }, 35)

  try {
    const resp = await fetch(`/api/minutes/generate?${params}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      signal: abortController.value.signal,
    })

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: '请求失败' }))
      resultText.value = `错误: ${err.detail || resp.statusText}`
      generating.value = false
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done: streamDone, value } = await reader.read()
      if (streamDone) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6).trim()
        if (!dataStr) continue
        try {
          const data = JSON.parse(dataStr)
          if (data.type === 'chunk') {
            pendingBuffer.value += data.text
          } else if (data.type === 'done') {
            // 完成：先清空 pendingBuffer，再标记 done
            if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
            // 立即显示剩余内容
            resultText.value += pendingBuffer.value
            pendingBuffer.value = ''
            resultText.value = data.text
            recordId.value = data.id
            if (data.preference_id) {
              // 刷新偏好列表
              try {
                const res = await listPreferences({ adopted: 1 })
                adoptedPrefs.value = (res.preferences || [])
              } catch { /* ignore */ }
            }
            if (data.usage) usage.value = data.usage.total_tokens
            generating.value = false
            done.value = true
            await nextTick()
            if (resultBody.value) {
              resultBody.value.scrollTop = resultBody.value.scrollHeight
            }
          } else if (data.type === 'error') {
            if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
            resultText.value += pendingBuffer.value
            pendingBuffer.value = ''
            resultText.value = `错误: ${data.message}`
            generating.value = false
          }
        } catch { /* ignore */ }
      }
    }
  } catch (e) {
    if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
    resultText.value += pendingBuffer.value
    pendingBuffer.value = ''
    if (e.name === 'AbortError') {
      resultText.value += '\n\n--- 已停止 ---'
    } else {
      resultText.value = `错误: ${e.message}`
    }
  } finally {
    generating.value = false
  }
}

function stopGenerate() {
  if (abortController.value) {
    abortController.value.abort()
  }
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
  resultText.value += pendingBuffer.value
  pendingBuffer.value = ''
}

function resetForm() {
  if (typingTimer) { clearInterval(typingTimer); typingTimer = null }
  resultText.value = ''
  usage.value = null
  done.value = false
  generating.value = false
  abortController.value = null
  pendingBuffer.value = ''
  recordId.value = null
  editing.value = false
  editText.value = ''
  showRegenDialog.value = false
  regenReason.value = ''
  regenNotes.value = ''
  regenPrefId.value = ''
}

// 重新生成
function doRegenerate() {
  if (!regenReason.value) return
  showRegenDialog.value = false
  regenerating.value = true
  startGenerate({
    reason: regenReason.value,
    notes: regenNotes.value,
    prefId: regenPrefId.value || selectedPrefId.value,
  })
  regenerating.value = false
}

// 编辑功能
function startEdit() {
  editText.value = resultText.value
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  editText.value = ''
}

function onEditInput() {
  // 实时更新预览
  resultText.value = editText.value
}

async function doSave() {
  if (!recordId.value || !editText.value.trim()) return
  saving.value = true
  try {
    await updateMinutes(recordId.value, { content: editText.value })
    resultText.value = editText.value
    editing.value = false
    toast.success('保存成功！')
  } catch (e) {
    toast.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

async function copyResult() {
  try {
    await navigator.clipboard.writeText(resultText.value)
    toast.success('已复制到剪贴板')
  } catch {
    const ta = document.createElement('textarea')
    ta.value = resultText.value
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(templatePrompts[meetingType.value])
    toast.success('提示词已复制')
  } catch {
    const ta = document.createElement('textarea')
    ta.value = templatePrompts[meetingType.value]
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
}
</script>

<style scoped>
.minutes-page { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.form-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 24px; margin-bottom: 24px; max-width: 800px; }
.field { margin-bottom: 16px; flex: 1; }
.field label { display: block; font-size: 0.85rem; color: #64748b; margin-bottom: 4px; }
.field .required { color: #dc2626; }
.form-select, .form-input { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; }
.form-select:focus, .form-input:focus { border-color: #4f46e5; }
.form-textarea { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; font-family: inherit; resize: vertical; }
.form-textarea:focus { border-color: #4f46e5; }
.field-row { display: flex; gap: 14px; }

/* ? 图标悬浮提示 */
.tip-icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px; border-radius: 50%;
  background: #cbd5e1; color: #fff; font-size: 0.65rem; font-weight: 700;
  cursor: help; vertical-align: middle; margin-left: 4px;
  position: relative; user-select: none;
  z-index: 1;
}
.tip-icon:hover { background: #94a3b8; }
.tip-icon::after {
  content: attr(data-tip);
  position: absolute; top: calc(100% + 6px); left: 0;
  background: #1e293b; color: #fff;
  font-size: 0.72rem; font-weight: 400; white-space: nowrap;
  padding: 5px 10px; border-radius: 6px;
  pointer-events: none; opacity: 0; transition: opacity 0.15s;
  z-index: 9999; line-height: 1.4;
}
.tip-icon:hover::after { opacity: 1; }

.selected-meeting { margin-top: 8px; padding: 8px 12px; background: #eef2ff; border-radius: 6px; font-size: 0.85rem; color: #4f46e5; }
.selected-meeting.muted { background: #f1f5f9; color: #94a3b8; }
.selected-task { margin-top: 6px; padding: 8px 12px; background: #f0fdf4; border-radius: 6px; font-size: 0.85rem; color: #16a34a; }
.meeting-link { color: #4f46e5; text-decoration: underline; cursor: pointer; }
.meeting-link:hover { color: #4338ca; }
.doc-badge { font-size: 0.75rem; background: #fff; padding: 1px 6px; border-radius: 3px; margin-left: 6px; }

.template-tabs { display: flex; gap: 4px; flex-wrap: wrap; }
.template-tab { padding: 6px 16px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #64748b; }
.template-tab.active { border-color: #4f46e5; color: #4f46e5; background: #eef2ff; }
.template-tab:hover { border-color: #4f46e5; }
.template-hint { margin-top: 6px; font-size: 0.78rem; color: #94a3b8; padding: 4px 8px; background: #f8fafc; border-radius: 4px; display: flex; align-items: center; gap: 8px; }
.btn-view-prompt { font-size: 0.75rem; padding: 2px 8px; border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; cursor: pointer; color: #4f46e5; white-space: nowrap; }
.btn-view-prompt:hover { background: #eef2ff; }

.form-actions { display: flex; gap: 12px; margin-top: 8px; }
.btn-generate { padding: 10px 28px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; font-size: 0.95rem; cursor: pointer; }
.btn-generate:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-generate:hover:not(:disabled) { background: #4338ca; }
.btn-stop { padding: 10px 28px; background: #dc2626; color: #fff; border: none; border-radius: 8px; font-size: 0.95rem; cursor: pointer; }
.btn-stop:hover { background: #b91c1c; }

/* 结果区 */
.result-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.result-header { display: flex; align-items: center; justify-content: space-between; padding: 14px 20px; border-bottom: 1px solid #e2e8f0; background: #f8fafc; }
.result-header h3 { margin: 0; font-size: 0.95rem; color: #1e293b; }
.result-actions { display: flex; align-items: center; gap: 12px; }
.btn-copy { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; cursor: pointer; font-size: 0.8rem; color: #64748b; }
.btn-copy:hover { border-color: #4f46e5; color: #4f46e5; }
.usage-info { font-size: 0.78rem; color: #94a3b8; }
.result-body { padding: 20px 24px; max-height: 600px; overflow-y: auto; }

/* Markdown 渲染 */
.markdown-content { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif; font-size: 15px; line-height: 1.8; color: #262626; word-wrap: break-word; }
.markdown-content :deep(h1) { font-size: 1.6em; font-weight: 600; margin: 1.2em 0 0.5em; padding-bottom: 0.3em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.markdown-content :deep(h2) { font-size: 1.4em; font-weight: 600; margin: 1em 0 0.4em; padding-bottom: 0.2em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.markdown-content :deep(h3) { font-size: 1.2em; font-weight: 600; margin: 0.8em 0 0.3em; color: #1a1a1a; }
.markdown-content :deep(p) { margin: 0.5em 0; }
.markdown-content :deep(strong) { font-weight: 600; color: #1a1a1a; }
.markdown-content :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
.markdown-content :deep(th), .markdown-content :deep(td) { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
.markdown-content :deep(th) { background: #f6f8fa; font-weight: 600; }
.markdown-content :deep(tr:nth-child(even)) { background: #fafbfc; }
.markdown-content :deep(ul), .markdown-content :deep(ol) { padding-left: 2em; margin: 0.5em 0; }
.markdown-content :deep(li) { margin: 0.3em 0; }
.markdown-content :deep(code) { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.88em; color: #d63384; }
.markdown-content :deep(pre) { background: #f6f8fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; overflow-x: auto; margin: 1em 0; }
.markdown-content :deep(pre code) { background: none; padding: 0; font-size: 0.85em; color: #1e293b; line-height: 1.5; }
.markdown-content :deep(blockquote) { margin: 1em 0; padding: 8px 16px; border-left: 4px solid #4f46e5; background: #f8fafc; color: #64748b; }

.cursor-blink { display: inline; animation: blink 1s step-end infinite; color: #4f46e5; font-size: 1.1rem; }
.generating-status { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 12px; padding: 40px 0; color: #94a3b8; font-size: 0.9rem; }
.done-banner { text-align: center; padding: 12px; color: #16a34a; font-size: 0.9rem; font-weight: 500; border-top: 1px solid #e2e8f0; margin-top: 12px; }
.btn-view-list { padding: 6px 16px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; font-size: 0.8rem; cursor: pointer; text-decoration: none; }
.btn-view-list:hover { background: #4338ca; }
.btn-generate-sm { padding: 6px 16px; background: #fff; color: #64748b; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.8rem; cursor: pointer; }
.btn-generate-sm:hover { border-color: #4f46e5; color: #4f46e5; }
.btn-edit { padding: 6px 16px; background: #fff; color: #64748b; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.8rem; cursor: pointer; }
.btn-edit:hover { border-color: #4f46e5; color: #4f46e5; }
.btn-regen { padding: 6px 16px; background: #d97706; color: #fff; border: none; border-radius: 6px; font-size: 0.8rem; cursor: pointer; }
.btn-regen:hover { background: #b45309; }
.btn-save { padding: 6px 16px; background: #16a34a; color: #fff; border: none; border-radius: 6px; font-size: 0.8rem; cursor: pointer; }
.btn-save:hover { background: #15803d; }
.btn-save:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-cancel-edit { padding: 6px 16px; background: #fff; color: #64748b; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.8rem; cursor: pointer; }
.btn-cancel-edit:hover { border-color: #dc2626; color: #dc2626; }
.edit-area { display: flex; flex-direction: column; gap: 8px; }
.edit-textarea { width: 100%; min-height: 400px; padding: 12px; border: 1px solid #4f46e5; border-radius: 6px; font-size: 0.85rem; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; line-height: 1.6; resize: vertical; outline: none; box-sizing: border-box; }
.edit-textarea:focus { border-color: #4338ca; }
.edit-hint { font-size: 0.75rem; color: #94a3b8; }
.pref-hint { margin-top: 6px; padding: 6px 10px; background: #fef3c7; border-radius: 4px; font-size: 0.78rem; color: #92400e; }

/* 重新生成弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.regen-modal { background: #fff; border-radius: 12px; width: 520px; max-width: 95vw; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }
.modal-header h3 { margin: 0; font-size: 1rem; color: #1e293b; }
.modal-close { width: 32px; height: 32px; border: none; background: none; font-size: 1.2rem; cursor: pointer; color: #94a3b8; border-radius: 6px; }
.modal-close:hover { background: #e2e8f0; color: #1e293b; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px; border-top: 1px solid #e2e8f0; }
.btn-cancel { padding: 8px 20px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #64748b; }
.btn-cancel:hover { border-color: #dc2626; color: #dc2626; }

/* 提示词预览弹窗 */
.prompt-modal { background: #fff; border-radius: 12px; width: 720px; max-width: 95vw; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.prompt-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }
.prompt-header h3 { margin: 0; font-size: 1rem; color: #1e293b; }
.prompt-header-actions { display: flex; align-items: center; gap: 8px; }
.btn-copy-prompt { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; cursor: pointer; font-size: 0.8rem; color: #64748b; }
.btn-copy-prompt:hover { border-color: #4f46e5; color: #4f46e5; }
.prompt-close { width: 32px; height: 32px; border: none; background: none; font-size: 1.2rem; cursor: pointer; color: #94a3b8; border-radius: 6px; }
.prompt-close:hover { background: #e2e8f0; color: #1e293b; }
.prompt-hint { padding: 8px 20px; font-size: 0.8rem; color: #94a3b8; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.prompt-body { flex: 1; overflow-y: auto; padding: 20px; margin: 0; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; font-size: 0.82rem; line-height: 1.6; color: #334155; white-space: pre-wrap; word-wrap: break-word; }
@keyframes blink { 50% { opacity: 0; } }
</style>