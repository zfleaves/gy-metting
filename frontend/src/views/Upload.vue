<template>
  <div class="upload-page">
    <div class="page-header">
      <h1>音频转写</h1>
      <p>支持 mp3、wav、m4a 格式，最大 200MB</p>
    </div>

    <!-- 关联会议选择 -->
    <div class="meeting-selector">
      <label>关联会议/需求</label>
      <select v-model="selectedMeetingId" class="meeting-select">
        <option value="">-- 不关联 --</option>
        <option v-for="m in meetings" :key="m.id" :value="m.id">
          {{ m.title }}（{{ m.snapshot_ids?.length || 0 }} 个文档）
        </option>
      </select>
    </div>

    <div class="upload-zone"
      :class="{ dragging, uploaded: !!uploadResult }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <!-- 初始：选择文件 -->
      <div v-if="!uploading && !uploadResult" class="upload-prompt">
        <div class="upload-icon">🎙️</div>
        <p>拖拽音频文件到此处，或点击选择</p>
        <input type="file" ref="fileInput" accept=".mp3,.wav,.m4a" @change="onFileSelect" hidden />
        <button class="btn-select" @click="$refs.fileInput.click()">选择文件</button>
      </div>

      <!-- 上传中 -->
      <div v-if="uploading" class="upload-progress">
        <div class="spinner"></div>
        <p>上传中...</p>
      </div>

      <!-- 上传成功区域 -->
      <div v-if="uploadResult" class="upload-success">
        <div class="check-icon">✓</div>
        <p>上传成功 <span style="color:#4f46e5;font-size:0.75rem;">[v3]</span></p>
        <div v-if="selectedMeetingId && selectedMeetingName" class="meeting-tag">
          📋 关联会议：{{ selectedMeetingName }}
        </div>
        <div class="file-info">
          <span>{{ uploadResult.filename }}</span>
          <span>{{ (uploadResult.size_bytes / 1024).toFixed(1) }} KB</span>
          <span>{{ uploadResult.format }}</span>
        </div>

        <!-- 状态 0：还没提交 → 显示按钮 -->
        <template v-if="viewState === 'idle'">
          <div class="action-row">
            <button class="btn-primary" @click="startTranscribe" :disabled="transcribing">
              <span v-if="transcribing" class="spinner-sm"></span>
              {{ transcribing ? '提交中...' : '开始转写' }}
            </button>
            <button class="btn-secondary" @click="resetUpload">重新上传</button>
          </div>
        </template>

        <!-- 状态 1：处理中 → 显示进度条 -->
        <template v-if="viewState === 'processing'">
          <div class="task-progress">
            <div class="progress-section">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: (taskProgress * 100) + '%' }"></div>
              </div>
              <div class="progress-text">{{ progressLabel(taskProgress) }}</div>
            </div>
            <p class="polling-hint">
              <span class="spinner-sm"></span>
              {{ pollingCount > 0 ? `已等待 ${pollingCount}s` : '自动刷新中...' }}
            </p>
          </div>
        </template>

        <!-- 状态 2：完成 → 查看结果 -->
        <template v-if="viewState === 'done'">
          <div class="task-link">
            <p>✅ 转写完成</p>
            <router-link :to="`/task/${taskId}`" class="btn-primary">查看转写结果 →</router-link>
          </div>
        </template>

        <!-- 状态 3：失败 -->
        <template v-if="viewState === 'error'">
          <div class="task-link">
            <p class="failed-text">❌ 转写失败</p>
            <p v-if="taskError" class="error-detail">{{ taskError }}</p>
            <button class="btn-secondary" @click="resetUpload">重新上传</button>
          </div>
        </template>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { uploadAudio, submitTask, getTask, listMeetings } from '../api.js'

const fileInput = ref(null)
const dragging = ref(false)
const uploading = ref(false)
const transcribing = ref(false)
const uploadResult = ref(null)
const taskId = ref(null)
const taskStatus = ref('')
const taskProgress = ref(0)
const taskError = ref('')
const pollingCount = ref(0)
const error = ref('')
const meetings = ref([])
const selectedMeetingId = ref('')
const selectedMeetingName = computed(() => {
  const m = meetings.value.find(m => m.id === selectedMeetingId.value)
  return m ? m.title : ''
})
let timer = null

// 用 computed 统一管理视图状态，避免多个 v-if 条件冲突
const viewState = computed(() => {
  if (!taskId.value) return 'idle'
  if (taskStatus.value === 'completed') return 'done'
  if (taskStatus.value === 'failed') return 'error'
  return 'processing'
})

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) processFile(file)
}

onMounted(async () => {
  try { meetings.value = await listMeetings() } catch { /* ignore */ }
})

function onFileSelect(e) {
  const file = e.target.files[0]
  if (file) processFile(file)
}

async function processFile(file) {
  error.value = ''
  const allowed = ['mp3', 'wav', 'm4a']
  const ext = file.name.split('.').pop().toLowerCase()
  if (!allowed.includes(ext)) {
    error.value = `不支持的格式: .${ext}，允许: ${allowed.join(', ')}`
    return
  }
  if (file.size > 200 * 1024 * 1024) {
    error.value = '文件过大，限制 200MB'
    return
  }
  uploading.value = true
  try {
    const result = await uploadAudio(file)
    uploadResult.value = result
  } catch (e) {
    error.value = '上传失败: ' + e.message
  } finally {
    uploading.value = false
  }
}

async function startTranscribe() {
  if (!uploadResult.value) return
  transcribing.value = true
  error.value = ''
  try {
    // 1. 提交任务 → 后端立刻返回 task_id（不等转写完成）
    const result = await submitTask('asr', { audio_path: uploadResult.value.path, meeting_id: selectedMeetingId.value || undefined }, uploadResult.value.filename)
    // 2. 拿到 task_id 后立刻更新界面，显示进度条
    taskId.value = result.task_id
    taskStatus.value = 'pending'
    taskProgress.value = 0
    // 3. 开始轮询进度
    startPolling()
  } catch (e) {
    error.value = '提交失败: ' + (e.message || '未知错误')
  } finally {
    transcribing.value = false
  }
}

function startPolling() {
  pollingCount.value = 0
  pollTask()
  timer = setInterval(() => {
    pollingCount.value += 2
    pollTask()
  }, 2000)
}

async function pollTask() {
  if (!taskId.value) return
  try {
    const t = await getTask(taskId.value)
    taskStatus.value = t.status
    taskProgress.value = t.progress || 0
    if (t.status === 'failed') {
      taskError.value = t.error_message || ''
      stopPolling()
    }
    if (t.status === 'completed') {
      taskProgress.value = 1.0
      stopPolling()
    }
  } catch (e) {
    // 轮询失败不中断
  }
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

function progressLabel(p) {
  if (p < 0.08) return '排队等待中...'
  if (p < 0.18) return '加载模型中...'
  if (p < 0.85) return `转写中...已完成 ${Math.round(p * 100)}%`
  if (p < 0.95) return '保存结果...'
  return '即将完成...'
}

function resetUpload() {
  stopPolling()
  uploadResult.value = null
  taskId.value = null
  taskStatus.value = ''
  taskProgress.value = 0
  taskError.value = ''
  error.value = ''
}

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.upload-page {
  padding: 24px;
}

.meeting-selector {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.meeting-selector label {
  font-size: 0.85rem;
  color: #64748b;
  white-space: nowrap;
}
.meeting-select {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
  background: #fff;
  max-width: 400px;
}
.meeting-select:focus {
  border-color: #4f46e5;
}
.meeting-tag {
  display: inline-block; margin-top: 8px; padding: 4px 12px;
  background: #eef2ff; color: #4f46e5; border-radius: 6px;
  font-size: 0.82rem;
}

.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 1.3rem; margin: 0 0 4px; color: #1a1a2e; }
.page-header p { color: #94a3b8; font-size: 0.9rem; }

.upload-zone {
  border: 2px dashed #cbd5e1;
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  transition: border-color 0.2s, background 0.2s;
  min-height: 200px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
@media (max-width: 640px) { .upload-zone { padding: 32px 16px; } }
.upload-zone.dragging { border-color: #4f46e5; background: #eef2ff; }
.upload-zone.uploaded { border-color: #22c55e; border-style: solid; }

.upload-icon { font-size: 3rem; margin-bottom: 12px; }
.upload-prompt p { color: #64748b; margin-bottom: 16px; }

.btn-select, .btn-primary, .btn-secondary {
  padding: 10px 24px; border-radius: 8px; font-size: 0.95rem;
  border: none; cursor: pointer; transition: all 0.2s;
}
.btn-select { background: #f1f5f9; color: #334155; }
.btn-primary { background: #4f46e5; color: #fff; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { background: #fff; color: #64748b; border: 1px solid #e2e8f0; }

.spinner, .spinner-sm {
  border: 3px solid #e2e8f0; border-top-color: #4f46e5;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
.spinner { width: 36px; height: 36px; margin: 0 auto 12px; }
.spinner-sm { width: 16px; height: 16px; display: inline-block; margin-right: 6px; vertical-align: middle; }
@keyframes spin { to { transform: rotate(360deg); } }

.check-icon {
  width: 48px; height: 48px; background: #dcfce7; color: #16a34a;
  border-radius: 50%; display: flex; align-items: center; justify-content: center;
  font-size: 1.5rem; margin: 0 auto 12px;
}

.file-info { display: flex; gap: 12px; margin: 12px 0; color: #64748b; font-size: 0.9rem; }
.action-row { display: flex; gap: 12px; margin-top: 16px; justify-content: center; }

.task-progress { width: 100%; margin-top: 20px; }
.progress-section { margin-bottom: 8px; }
.progress-bar { width: 100%; height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
.progress-fill {
  height: 100%; background: linear-gradient(90deg, #4f46e5, #7c3aed);
  border-radius: 4px; transition: width 0.5s ease;
}
.progress-text { font-size: 0.85rem; color: #64748b; margin-top: 6px; }
.polling-hint { color: #94a3b8; font-size: 0.8rem; margin-top: 8px; }

.task-link { margin-top: 16px; }
.task-link p { color: #64748b; margin-bottom: 8px; }
.task-link .btn-primary { display: inline-block; text-decoration: none; }
.failed-text { color: #dc2626 !important; font-weight: 600; }
.error-detail { color: #94a3b8; font-size: 0.85rem; margin-bottom: 12px; max-width: 400px; word-break: break-all; }

.error-msg { color: #dc2626; background: #fef2f2; padding: 8px 16px; border-radius: 6px; margin-top: 12px; }
</style>