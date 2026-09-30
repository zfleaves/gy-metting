<template>
  <div class="task-page">
    <div class="page-header">
      <h1>任务详情</h1>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <p>加载中...</p>
    </div>

    <div v-else-if="!task" class="error">
      任务不存在
    </div>

    <div v-else class="task-detail">
      <div class="status-card" :class="task.status">
        <div class="status-badge">{{ statusLabel(task.status) }}</div>
        <div v-if="task.name" class="task-title">{{ task.name }}</div>
        <div class="task-meta">
          <div><span class="label">任务 ID</span> {{ task.id }}</div>
          <div><span class="label">类型</span> {{ task.type }}</div>
          <div v-if="task.created_at"><span class="label">创建时间</span> {{ formatTime(task.created_at) }}</div>
          <div v-if="task.completed_at"><span class="label">完成时间</span> {{ formatTime(task.completed_at) }}</div>
          <div v-if="task.meeting_id && associatedMeeting"><span class="label">关联会议</span> {{ associatedMeeting.title }}</div>
        </div>

        <div v-if="task.status === 'processing'" class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: (task.progress * 100) + '%' }"></div>
          </div>
          <div class="progress-text">{{ progressLabel(task.progress) }}</div>
        </div>
      </div>

      <div class="action-bar">
        <el-button type="primary" v-if="task.status === 'completed'" @click="$router.push(`/minutes/new?task_id=${task.id}`)">
          📝 生成纪要
        </el-button>
      </div>

      <div v-if="task.status === 'failed' && task.error_message" class="error-card">
        <h3>错误信息</h3>
        <pre>{{ task.error_message }}</pre>
      </div>

      <div v-if="task.status === 'completed' && parsedResult" class="result-card">
        <div v-if="audioUrl" class="audio-player">
          <el-button class="play-btn" circle @click="togglePlay">
            {{ playing ? '⏸' : '▶' }}
          </el-button>
          <div class="audio-bar" @click="seekAudio">
            <div class="audio-progress" :style="{ width: (currentTime / duration * 100) + '%' }"></div>
          </div>
          <span class="audio-time">{{ formatSegTime(currentTime) }} / {{ formatSegTime(duration) }}</span>
        </div>

        <h3>转写结果（{{ parsedResult.segments_count || segments.length }} 段，{{ parsedResult.duration_seconds?.toFixed(0) || 0 }}秒）</h3>

        <div class="toggle-row">
          <div class="view-tabs">
            <button class="view-tab" :class="{ active: viewMode === 'segments' }" @click="viewMode = 'segments'">分段对照</button>
            <button class="view-tab" :class="{ active: viewMode === 'fulltext' }" @click="viewMode = 'fulltext'">全文预览</button>
          </div>
          <el-button size="small" @click="autoHighlight" :disabled="autoMarking" :loading="autoMarking">
            🔄 重新自动标记
          </el-button>
        </div>

        <div class="toggle-row">
          <label class="toggle-label" :class="{ on: showHighlights }" @click="showHighlights = !showHighlights">
            <span class="toggle-switch"></span>
            重点高亮
          </label>
          <label class="toggle-label" :class="{ on: hideTrivial }" @click="hideTrivial = !hideTrivial">
            <span class="toggle-switch"></span>
            折叠旁支
          </label>
          <span v-if="hideTrivial && segments.length > filteredSegments.length" class="filtered-count">
            （已折叠 {{ segments.length - filteredSegments.length }} 段旁支）
          </span>
        </div>

        <div v-if="viewMode === 'segments' && filteredSegments.length" class="segments-list">
          <div
            v-for="(seg, i) in filteredSegments"
            :key="i"
            class="segment-item"
            :class="{ active: activeSegment === i, highlighted: displayHighlights.has(i) }"
          >
            <button class="highlight-btn" :class="{ on: highlightedIndices.has(i) }"
              @click.stop="toggleHighlight(i)" :title="highlightedIndices.has(i) ? '取消标记' : '标记为重点'">
              {{ highlightedIndices.has(i) ? '★' : '☆' }}
            </button>
            <span class="seg-time" @click="seekTo(seg.start)">{{ formatSegTime(seg.start) }} - {{ formatSegTime(seg.end) }}</span>
            <span class="seg-text" :class="{ editing: editingIndex === i }">
              <template v-if="editingIndex === i">
                <el-input v-model="editText" size="small" style="width: auto; flex: 1" @keyup.enter="saveEdit(i)" @keyup.escape="cancelEdit" />
                <el-button size="small" @click="saveEdit(i)">✓</el-button>
                <el-button size="small" @click="cancelEdit">✕</el-button>
              </template>
              <template v-else>
                {{ seg.text }}
              </template>
            </span>
            <span class="seg-actions">
              <el-button size="small" @click.stop="startEdit(i, seg.text)" title="纠正文字">✎</el-button>
              <el-button size="small" @click.stop="markFluff(i, seg.text)" title="标记为废话">🗑</el-button>
            </span>
          </div>
        </div>

        <div v-else-if="viewMode === 'segments' && parsedResult.text_preview" class="result-text">{{ parsedResult.text_preview }}</div>

        <div v-if="viewMode === 'fulltext'" class="fulltext-view">
          <div class="fulltext-content">
            <span
              v-for="(seg, i) in segments"
              :key="i"
              class="fulltext-seg"
              :class="{
                highlighted: displayHighlights.has(i),
                active: activeSegment === i,
                hidden: hideTrivial && isTrivial(seg.text)
              }"
              @click="seekTo(seg.start)"
              :title="formatSegTime(seg.start)"
            >{{ seg.text }} </span>
          </div>
        </div>

        <div v-if="parsedResult.result_path" class="result-path">
          完整文件: {{ parsedResult.result_path }}
        </div>
      </div>

      <div v-if="task.status === 'pending' || task.status === 'processing'" class="polling-hint">
        <span class="spinner-sm"></span>
        任务处理中，{{ pollingCount > 0 ? `已等待 ${pollingCount}s` : '自动刷新中...' }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { getTask, getTaskSegments, getHighlights, saveHighlights, addCorrection, addFluff, getMeeting } from '../api.js'

const route = useRoute()
const task = ref(null)
const segments = ref([])
const highlightedIndices = ref(new Set())
const showHighlights = ref(true)
const hideTrivial = ref(true)
const ignoreKeywords = ref([])
const viewMode = ref('segments')
const loading = ref(true)
const associatedMeeting = ref(null)
const pollingCount = ref(0)
let timer = null

const audio = ref(null)
const playing = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const activeSegment = ref(-1)

const parsedResult = computed(() => {
  if (!task.value?.result_summary) return null
  try {
    return JSON.parse(task.value.result_summary)
  } catch {
    return { text_preview: task.value.result_summary }
  }
})

const audioUrl = computed(() => {
  const path = parsedResult.value?.audio_path
  if (!path) return null
  const match = path.match(/[\\/]([a-f0-9]{16})\./)
  if (match) {
    return `/api/audio/${match[1]}`
  }
  return null
})

const filteredSegments = computed(() => {
  if (!hideTrivial.value || !ignoreKeywords.value.length) return segments.value
  return segments.value.filter(seg => {
    for (const kw of ignoreKeywords.value) {
      if (seg.text.includes(kw)) return false
    }
    return true
  })
})

const displayHighlights = computed(() => {
  return showHighlights.value ? highlightedIndices.value : new Set()
})

function initAudio() {
  if (!audioUrl.value) return
  audio.value = new Audio(audioUrl.value)
  audio.value.addEventListener('timeupdate', onTimeUpdate)
  audio.value.addEventListener('loadedmetadata', () => {
    duration.value = audio.value.duration || 0
  })
  audio.value.addEventListener('ended', () => {
    playing.value = false
    activeSegment.value = -1
  })
  audio.value.addEventListener('play', () => { playing.value = true })
  audio.value.addEventListener('pause', () => { playing.value = false })
}

function togglePlay() {
  if (!audio.value) return
  if (audio.value.paused) {
    audio.value.play()
  } else {
    audio.value.pause()
  }
}

function seekTo(seconds) {
  if (!audio.value) return
  audio.value.currentTime = seconds
  if (audio.value.paused) {
    audio.value.play()
  }
}

function seekAudio(e) {
  if (!audio.value || !duration.value) return
  const rect = e.currentTarget.getBoundingClientRect()
  const ratio = (e.clientX - rect.left) / rect.width
  audio.value.currentTime = ratio * duration.value
  if (audio.value.paused) {
    audio.value.play()
  }
}

function onTimeUpdate() {
  if (!audio.value) return
  currentTime.value = audio.value.currentTime
  const segs = hideTrivial.value ? filteredSegments.value : segments.value
  if (!segs.length) return
  let found = -1
  for (let i = 0; i < segs.length; i++) {
    if (currentTime.value >= segs[i].start && currentTime.value < segs[i].end) {
      found = i
      break
    }
  }
  activeSegment.value = found
}

async function fetchTask() {
  try {
    task.value = await getTask(route.params.id)
    if (task.value.meeting_id) {
      try {
        associatedMeeting.value = await getMeeting(task.value.meeting_id)
      } catch { /* ignore */ }
    }
    if (task.value.status === 'completed') {
      try {
        const segData = await getTaskSegments(route.params.id)
        segments.value = segData.segments || []
      } catch { /* ignore */ }
      try {
        const hlData = await getHighlights(route.params.id)
        highlightedIndices.value = new Set(hlData.highlighted_indices || [])
      } catch { /* ignore */ }
      try {
        const kwRes = await fetch(`/api/tasks/${route.params.id}/auto-highlight-keywords`)
        const kwData = await kwRes.json()
        ignoreKeywords.value = kwData.ignore_keywords || []
      } catch { /* ignore */ }
    }
    if (task.value.status === 'pending' || task.value.status === 'processing') {
      pollingCount.value++
    }
  } catch {
    task.value = null
  } finally {
    loading.value = false
  }
}

watch(parsedResult, (val) => {
  if (val?.audio_path && !audio.value) {
    initAudio()
  }
})

onMounted(() => {
  fetchTask()
  timer = setInterval(() => {
    if (task.value && (task.value.status === 'pending' || task.value.status === 'processing')) {
      fetchTask()
    }
  }, 2000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  if (audio.value) {
    audio.value.pause()
    audio.value.src = ''
  }
})

function statusLabel(s) {
  const map = { pending: '等待中', processing: '处理中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t + 'Z')
  return d.toLocaleString('zh-CN')
}

function formatSegTime(seconds) {
  if (!seconds && seconds !== 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function progressLabel(p) {
  if (p < 0.08) return '排队等待中...'
  if (p < 0.18) return '加载模型中...'
  if (p < 0.85) return `转写中...已完成 ${Math.round(p * 100)}%`
  if (p < 0.95) return '保存结果...'
  return '即将完成...'
}

async function toggleHighlight(index) {
  if (highlightedIndices.value.has(index)) {
    highlightedIndices.value.delete(index)
  } else {
    highlightedIndices.value.add(index)
  }
  highlightedIndices.value = new Set(highlightedIndices.value)
  try {
    await saveHighlights(route.params.id, [...highlightedIndices.value])
  } catch { /* ignore */ }
}

const autoMarking = ref(false)

const editingIndex = ref(-1)
const editText = ref('')

function startEdit(index, text) {
  editingIndex.value = index
  editText.value = text
}

function cancelEdit() {
  editingIndex.value = -1
  editText.value = ''
}

async function saveEdit(index) {
  const oldText = segments.value[index]?.text || ''
  const newText = editText.value.trim()
  if (!newText || newText === oldText) {
    cancelEdit()
    return
  }
  try {
    await addCorrection(oldText, newText)
  } catch { /* ignore */ }
  segments.value[index] = { ...segments.value[index], text: newText }
  cancelEdit()
}

async function markFluff(index, text) {
  try {
    await addFluff(text)
    hideTrivial.value = true
    if (!ignoreKeywords.value.includes(text)) {
      ignoreKeywords.value.push(text)
    }
  } catch { /* ignore */ }
}

function isTrivial(text) {
  if (!ignoreKeywords.value.length) return false
  for (const kw of ignoreKeywords.value) {
    if (text.includes(kw)) return true
  }
  return false
}

async function autoHighlight() {
  autoMarking.value = true
  try {
    const res = await fetch(`/api/tasks/${route.params.id}/auto-highlight-keywords`)
    const { keywords } = await res.json()
    const newSet = new Set(highlightedIndices.value)
    segments.value.forEach((seg, i) => {
      for (const kw of keywords) {
        if (seg.text.includes(kw)) {
          newSet.add(i)
          break
        }
      }
    })
    highlightedIndices.value = newSet
    await saveHighlights(route.params.id, [...newSet])
  } catch { /* ignore */ }
  finally {
    autoMarking.value = false
  }
}
</script>

<style scoped>
.task-page { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 1.3rem; margin: 0; color: #1a1a2e; }
.loading, .error { text-align: center; padding: 48px; color: #64748b; }
.spinner, .spinner-sm { border: 3px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; }
.spinner { width: 36px; height: 36px; margin: 0 auto 12px; }
.spinner-sm { width: 14px; height: 14px; display: inline-block; margin-right: 6px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }

.audio-player { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: #1a1a2e; border-radius: 10px; margin-bottom: 16px; }
.play-btn { flex-shrink: 0; }
.audio-bar { flex: 1; height: 6px; background: #334155; border-radius: 3px; cursor: pointer; position: relative; overflow: hidden; }
.audio-progress { height: 100%; background: #4f46e5; border-radius: 3px; transition: width 0.1s linear; }
.audio-time { color: #94a3b8; font-size: 0.8rem; white-space: nowrap; }

.status-card { padding: 20px; border-radius: 12px; margin-bottom: 16px; }
.status-card.completed { background: #f0fdf4; border: 1px solid #bbf7d0; }
.status-card.failed { background: #fef2f2; border: 1px solid #fecaca; }
.status-card.processing { background: #fefce8; border: 1px solid #fef08a; }
.status-card.pending { background: #f8fafc; border: 1px solid #e2e8f0; }
.action-bar { margin: 16px 0; display: flex; gap: 8px; }
.status-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.9rem; font-weight: 500; margin-bottom: 12px; }
.status-card.completed .status-badge { background: #16a34a; color: #fff; }
.status-card.failed .status-badge { background: #dc2626; color: #fff; }
.status-card.processing .status-badge { background: #ca8a04; color: #fff; }
.status-card.pending .status-badge { background: #64748b; color: #fff; }
.task-title { font-size: 1.1rem; font-weight: 600; color: #1e293b; margin-bottom: 12px; word-break: break-all; }
.task-meta { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 0.9rem; }
.label { color: #94a3b8; margin-right: 6px; }
.progress-section { margin-top: 12px; }
.progress-bar { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
.progress-fill { height: 100%; background: #4f46e5; border-radius: 3px; transition: width 0.5s; }
.progress-text { font-size: 0.8rem; color: #64748b; margin-top: 4px; }

.error-card { background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px; padding: 16px; margin-bottom: 16px; }
.error-card h3 { color: #dc2626; margin: 0 0 8px; font-size: 1rem; }
.error-card pre { white-space: pre-wrap; font-size: 0.85rem; color: #7f1d1d; margin: 0; }

.result-card { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px; }
.result-card h3 { margin: 0 0 12px; font-size: 1rem; color: #334155; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; }

.view-tabs { display: flex; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; }
.view-tab { padding: 5px 14px; border: none; background: #fff; color: #64748b; font-size: 0.8rem; cursor: pointer; transition: all 0.15s; }
.view-tab + .view-tab { border-left: 1px solid #e2e8f0; }
.view-tab.active { background: #4f46e5; color: #fff; }
.view-tab:hover:not(.active) { background: #f1f5f9; }

.fulltext-view { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 20px; max-height: 500px; overflow-y: auto; }
.fulltext-content { line-height: 2; font-size: 0.95rem; color: #334155; white-space: pre-wrap; }
.fulltext-seg { cursor: pointer; border-radius: 2px; transition: background 0.1s; }
.fulltext-seg:hover { background: #eef2ff; }
.fulltext-seg.highlighted { background: #fffbeb; border-bottom: 2px solid #f59e0b; }
.fulltext-seg.active { background: #4f46e5; color: #fff; }
.fulltext-seg.hidden { opacity: 0.2; font-size: 0.8rem; }

.toggle-row { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-wrap: wrap; }
.toggle-label { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; color: #64748b; cursor: pointer; user-select: none; }
.toggle-label.on { color: #334155; }
.toggle-switch { width: 32px; height: 18px; background: #d1d5db; border-radius: 9px; position: relative; transition: background 0.2s; }
.toggle-switch::after { content: ''; width: 14px; height: 14px; background: #fff; border-radius: 50%; position: absolute; top: 2px; left: 2px; transition: transform 0.2s; }
.toggle-label.on .toggle-switch { background: #4f46e5; }
.toggle-label.on .toggle-switch::after { transform: translateX(14px); }
.filtered-count { font-size: 0.75rem; color: #94a3b8; }
.result-text { white-space: pre-wrap; line-height: 1.7; color: #334155; }

.segments-list { display: flex; flex-direction: column; gap: 6px; max-height: 500px; overflow-y: auto; }
.segment-item { display: flex; gap: 8px; padding: 8px 10px; background: #fff; border-radius: 6px; border: 1px solid #e2e8f0; align-items: flex-start; cursor: pointer; transition: all 0.15s; }
.segment-item:hover { border-color: #c7d2fe; background: #eef2ff; }
.segment-item.active { border-color: #4f46e5; background: #eef2ff; box-shadow: 0 0 0 1px #4f46e5; }
.segment-item.highlighted { background: #fffbeb; border-color: #f59e0b; }
.segment-item.highlighted.active { border-color: #4f46e5; background: #eef2ff; border-left: 3px solid #f59e0b; }
.highlight-btn { background: none; border: none; cursor: pointer; font-size: 1.1rem; padding: 0 2px; line-height: 1; color: #d1d5db; transition: color 0.15s; flex-shrink: 0; }
.highlight-btn:hover { color: #f59e0b; }
.highlight-btn.on { color: #f59e0b; }
.seg-time { color: #4f46e5; font-size: 0.8rem; white-space: nowrap; padding-top: 1px; min-width: 80px; flex-shrink: 0; }
.seg-text { color: #334155; line-height: 1.6; flex: 1; display: flex; align-items: center; gap: 4px; }
.seg-actions { display: flex; gap: 4px; opacity: 0; transition: opacity 0.15s; flex-shrink: 0; }
.segment-item:hover .seg-actions { opacity: 1; }
.result-path { margin-top: 12px; font-size: 0.8rem; color: #94a3b8; }
.polling-hint { text-align: center; padding: 16px; color: #64748b; font-size: 0.9rem; }
</style>