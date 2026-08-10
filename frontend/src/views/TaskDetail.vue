<template>
  <div class="task-page">
    <div class="page-header">
      <router-link to="/" class="back-link">← 返回</router-link>
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
      <!-- 状态卡片 -->
      <div class="status-card" :class="task.status">
        <div class="status-badge">{{ statusLabel(task.status) }}</div>
        <div class="task-meta">
          <div><span class="label">任务 ID</span> {{ task.id }}</div>
          <div><span class="label">类型</span> {{ task.type }}</div>
          <div v-if="task.created_at"><span class="label">创建时间</span> {{ formatTime(task.created_at) }}</div>
          <div v-if="task.completed_at"><span class="label">完成时间</span> {{ formatTime(task.completed_at) }}</div>
        </div>

        <div v-if="task.status === 'processing'" class="progress-section">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: (task.progress * 100) + '%' }"></div>
            </div>
            <div class="progress-text">{{ progressLabel(task.progress) }}</div>
          </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="task.status === 'failed' && task.error_message" class="error-card">
        <h3>错误信息</h3>
        <pre>{{ task.error_message }}</pre>
      </div>

      <!-- 转写结果 -->
      <div v-if="task.status === 'completed' && parsedResult" class="result-card">
        <!-- 音频播放器 -->
        <div v-if="audioUrl" class="audio-player">
          <button class="play-btn" @click="togglePlay">
            {{ playing ? '⏸' : '▶' }}
          </button>
          <div class="audio-bar" @click="seekAudio">
            <div class="audio-progress" :style="{ width: (currentTime / duration * 100) + '%' }"></div>
          </div>
          <span class="audio-time">{{ formatSegTime(currentTime) }} / {{ formatSegTime(duration) }}</span>
        </div>

        <h3>转写结果（{{ parsedResult.segments_count || segments.length }} 段，{{ parsedResult.duration_seconds?.toFixed(0) || 0 }}秒）</h3>

        <!-- 分段时间轴 -->
        <div v-if="segments.length" class="segments-list">
          <div
            v-for="(seg, i) in segments"
            :key="i"
            class="segment-item"
            :class="{ active: activeSegment === i, highlighted: highlightedIndices.has(i) }"
            @click="seekTo(seg.start)"
          >
            <button class="highlight-btn" :class="{ on: highlightedIndices.has(i) }"
              @click.stop="toggleHighlight(i)" :title="highlightedIndices.has(i) ? '取消标记' : '标记为重点'">
              {{ highlightedIndices.has(i) ? '★' : '☆' }}
            </button>
            <span class="seg-time">{{ formatSegTime(seg.start) }} - {{ formatSegTime(seg.end) }}</span>
            <span class="seg-text">{{ seg.text }}</span>
          </div>
        </div>

        <div v-else-if="parsedResult.text_preview" class="result-text">{{ parsedResult.text_preview }}</div>

        <div v-if="parsedResult.result_path" class="result-path">
          完整文件: {{ parsedResult.result_path }}
        </div>
      </div>

      <!-- 轮询 -->
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
import { getTask, getTaskSegments, getHighlights, saveHighlights } from '../api.js'

const route = useRoute()
const task = ref(null)
const segments = ref([])
const highlightedIndices = ref(new Set())
const loading = ref(true)
const pollingCount = ref(0)
let timer = null

// 音频播放
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

// 从音频路径提取 file_id，构造音频 URL
const audioUrl = computed(() => {
  const path = parsedResult.value?.audio_path
  if (!path) return null
  // 路径格式: .../audio/4164d0b5c14d4472.wav → 提取 4164d0b5c14d4472
  const match = path.match(/[\\/]([a-f0-9]{16})\./)
  if (match) {
    return `/api/audio/${match[1]}`
  }
  return null
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
  if (!segments.value.length) return
  let found = -1
  for (let i = 0; i < segments.value.length; i++) {
    if (currentTime.value >= segments.value[i].start && currentTime.value < segments.value[i].end) {
      found = i
      break
    }
  }
  activeSegment.value = found
}

async function fetchTask() {
  try {
    task.value = await getTask(route.params.id)
    // 任务完成后加载分段
    if (task.value.status === 'completed') {
      try {
        const segData = await getTaskSegments(route.params.id)
        segments.value = segData.segments || []
      } catch {
        // 分段加载失败，显示纯文本
      }
      try {
        const hlData = await getHighlights(route.params.id)
        highlightedIndices.value = new Set(hlData.highlighted_indices || [])
      } catch {
        // 忽略
      }
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

// 当结果加载完成后初始化音频
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
  return new Date(t).toLocaleString('zh-CN')
}

function formatSegTime(seconds) {
  if (!seconds && seconds !== 0) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}

function progressLabel(p) {
  if (p < 0.15) return '加载模型中...'
  if (p < 0.3) return '转写中...'
  if (p < 0.95) return '保存结果...'
  return '即将完成...'
}

async function toggleHighlight(index) {
  if (highlightedIndices.value.has(index)) {
    highlightedIndices.value.delete(index)
  } else {
    highlightedIndices.value.add(index)
  }
  // 触发响应式更新
  highlightedIndices.value = new Set(highlightedIndices.value)
  // 保存到后端
  try {
    await saveHighlights(route.params.id, [...highlightedIndices.value])
  } catch {
    // 保存失败忽略
  }
}
</script>

<style scoped>
.task-page {
  max-width: 720px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.back-link {
  color: #4f46e5;
  text-decoration: none;
  font-size: 0.9rem;
}

.page-header h1 {
  font-size: 1.5rem;
  margin: 8px 0 4px;
  color: #1a1a2e;
}

.loading, .error {
  text-align: center;
  padding: 48px;
  color: #64748b;
}

.spinner, .spinner-sm {
  border: 3px solid #e2e8f0;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner { width: 36px; height: 36px; margin: 0 auto 12px; }
.spinner-sm { width: 14px; height: 14px; display: inline-block; margin-right: 6px; vertical-align: middle; }

@keyframes spin { to { transform: rotate(360deg); } }

/* 音频播放器 */
.audio-player {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #1a1a2e;
  border-radius: 10px;
  margin-bottom: 16px;
}

.play-btn {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: #4f46e5;
  color: #fff;
  font-size: 1.2rem;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  flex-shrink: 0;
}

.play-btn:hover {
  background: #4338ca;
}

.audio-bar {
  flex: 1;
  height: 6px;
  background: #334155;
  border-radius: 3px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
}

.audio-progress {
  height: 100%;
  background: #4f46e5;
  border-radius: 3px;
  transition: width 0.1s linear;
}

.audio-time {
  color: #94a3b8;
  font-size: 0.8rem;
  font-family: var(--mono);
  white-space: nowrap;
}

/* 状态卡片 */
.status-card {
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.status-card.completed { background: #f0fdf4; border: 1px solid #bbf7d0; }
.status-card.failed { background: #fef2f2; border: 1px solid #fecaca; }
.status-card.processing { background: #fefce8; border: 1px solid #fef08a; }
.status-card.pending { background: #f8fafc; border: 1px solid #e2e8f0; }

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 500;
  margin-bottom: 12px;
}

.status-card.completed .status-badge { background: #16a34a; color: #fff; }
.status-card.failed .status-badge { background: #dc2626; color: #fff; }
.status-card.processing .status-badge { background: #ca8a04; color: #fff; }
.status-card.pending .status-badge { background: #64748b; color: #fff; }

.task-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  font-size: 0.9rem;
}

.label {
  color: #94a3b8;
  margin-right: 6px;
}

.progress-section {
  margin-top: 12px;
}

.progress-bar {
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #4f46e5;
  border-radius: 3px;
  transition: width 0.5s;
}

.progress-text {
  font-size: 0.8rem;
  color: #64748b;
  margin-top: 4px;
}

.error-card {
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
}

.error-card h3 {
  color: #dc2626;
  margin: 0 0 8px;
  font-size: 1rem;
}

.error-card pre {
  white-space: pre-wrap;
  font-size: 0.85rem;
  color: #7f1d1d;
  margin: 0;
}

.result-card {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 16px;
}

.result-card h3 {
  margin: 0 0 12px;
  font-size: 1rem;
  color: #334155;
}

.result-text {
  white-space: pre-wrap;
  line-height: 1.7;
  color: #334155;
}

.segments-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: 500px;
  overflow-y: auto;
}

.segment-item {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  background: #fff;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  align-items: flex-start;
  cursor: pointer;
  transition: all 0.15s;
}

.segment-item:hover {
  border-color: #c7d2fe;
  background: #eef2ff;
}

.segment-item.active {
  border-color: #4f46e5;
  background: #eef2ff;
  box-shadow: 0 0 0 1px #4f46e5;
}

.segment-item.highlighted {
  background: #fffbeb;
  border-color: #f59e0b;
}

.segment-item.highlighted.active {
  border-color: #4f46e5;
  background: #eef2ff;
  border-left: 3px solid #f59e0b;
}

.highlight-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.1rem;
  padding: 0 2px;
  line-height: 1;
  color: #d1d5db;
  transition: color 0.15s;
  flex-shrink: 0;
}

.highlight-btn:hover {
  color: #f59e0b;
}

.highlight-btn.on {
  color: #f59e0b;
}

.seg-time {
  color: #4f46e5;
  font-size: 0.8rem;
  font-family: var(--mono);
  white-space: nowrap;
  padding-top: 1px;
  min-width: 80px;
}

.seg-text {
  color: #334155;
  line-height: 1.6;
}

.result-path {
  margin-top: 12px;
  font-size: 0.8rem;
  color: #94a3b8;
}

.polling-hint {
  text-align: center;
  padding: 16px;
  color: #64748b;
  font-size: 0.9rem;
}
</style>