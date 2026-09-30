<template>
  <div class="upload-page">
    <div class="page-header">
      <h1>音频转写</h1>
      <p>支持 mp3、wav、m4a 格式，最大 200MB；也可直接浏览器录音</p>
    </div>

    <!-- 关联会议选择 -->
    <div class="meeting-selector">
      <label>关联会议/需求</label>
      <el-select v-model="selectedMeetingId" placeholder="-- 不关联 --" style="flex: 1" clearable filterable>
        <el-option v-for="m in meetings" :key="m.id" :value="m.id" :label="`${m.title}（${m.snapshot_ids?.length || 0} 个文档）`" />
      </el-select>
      <el-button @click="showNewMeeting = true">+ 新增会议</el-button>
    </div>

    <!-- 新增会议弹窗 -->
    <CreateMeetingModal
      :visible="showNewMeeting"
      @close="showNewMeeting = false"
      @saved="onMeetingCreated"
    />

    <!-- ====== 方式一：上传文件 ====== -->
    <div class="section-title">📁 上传音频文件</div>
    <div class="upload-zone"
      :class="{ dragging, 'has-files': uploadedFiles.length > 0 }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <!-- 隐藏的文件输入（始终在 DOM 中，供多个按钮触发） -->
      <input type="file" ref="fileInput" accept=".mp3,.wav,.m4a" @change="onFileSelect" multiple hidden />

      <!-- 空状态：拖拽区 -->
      <div v-if="uploadedFiles.length === 0 && !uploading" class="upload-prompt">
        <div class="upload-icon">🎙️</div>
        <p>拖拽音频文件到此处，或点击选择（支持多文件）</p>
        <el-button type="primary" size="large" @click="$refs.fileInput.click()">选择文件</el-button>
      </div>

      <!-- 上传中 -->
      <div v-if="uploading" class="upload-progress">
        <div class="spinner"></div>
        <p>{{ uploadStatusText }}</p>
      </div>

      <!-- 文件列表（已上传） -->
      <div v-if="uploadedFiles.length > 0" class="file-list-wrap">
        <div class="file-list-header">
          <span class="file-count">已上传 {{ uploadedFiles.length }} 个文件</span>
          <div v-if="selectedMeetingId && selectedMeetingName" class="meeting-tag-mini">
            📋 {{ selectedMeetingName }}
          </div>
        </div>

        <div class="file-list">
          <div v-for="(f, idx) in uploadedFiles" :key="f.file_id"
            class="file-row"
            :class="{ 'drag-over': dragOverIdx === idx, 'dragging-src': draggingIdx === idx }"
            draggable="true"
            @dragstart="onDragStart(idx, $event)"
            @dragover.prevent="onDragOver(idx)"
            @dragleave="onDragLeave(idx)"
            @drop="onDropFile(idx)"
            @dragend="onDragEnd"
          >
            <span class="drag-handle" title="拖拽排序">⠿</span>
            <span class="file-order">{{ idx + 1 }}</span>
            <span class="file-name" :title="f.filename">{{ f.filename }}</span>
            <span class="file-size">{{ (f.size_bytes / 1024 / 1024).toFixed(1) }} MB</span>
            <span class="file-format">{{ f.format }}</span>
            <div class="file-actions">
              <el-button size="small" :disabled="idx === 0" @click="moveUp(idx)" title="上移">↑</el-button>
              <el-button size="small" :disabled="idx === uploadedFiles.length - 1" @click="moveDown(idx)" title="下移">↓</el-button>
              <el-button size="small" @click="removeFile(idx)" title="移除">✕</el-button>
            </div>
          </div>
        </div>

        <!-- 操作栏 -->
        <div v-if="batchAllDone" class="batch-all-done">
          <p>✅ 全部转写完成</p>
          <div v-for="bt in batchTasks" :key="bt.task_id" class="batch-task-link">
            <router-link :to="`/task/${bt.task_id}`">
              <el-button size="small" type="primary">查看「{{ bt.name }}」转写结果 →</el-button>
            </router-link>
            <router-link :to="`/minutes/new?task_id=${bt.task_id}`">
              <el-button size="small" type="success">📝 生成纪要</el-button>
            </router-link>
          </div>
          <el-button size="small" @click="resetUpload">重新上传</el-button>
        </div>

        <div v-else-if="batchTranscribing" class="batch-progress">
          <div class="batch-progress-header">
            <span class="spinner-sm"></span>
            转写进度：{{ batchDoneCount }} / {{ batchTasks.length }}
          </div>
          <div class="batch-task-list">
            <div v-for="bt in batchTasks" :key="bt.task_id" class="batch-task-row" :class="'batch-' + bt.status">
              <span class="batch-task-icon">{{ taskIcon(bt.status) }}</span>
              <span class="batch-task-name">{{ bt.name }}</span>
              <span class="batch-task-status">{{ bt.statusText }}</span>
              <div v-if="bt.status === 'processing'" class="batch-progress-bar">
                <div class="progress-fill" :style="{ width: (bt.progress * 100) + '%' }"></div>
              </div>
            </div>
          </div>
          <p v-if="batchPollingCount > 0" class="polling-hint">
            已等待 {{ formatDuration(batchPollingCount) }}
          </p>
        </div>

        <div v-else class="file-list-actions">
          <el-button size="small" @click="$refs.fileInput.click()">+ 继续添加</el-button>
          <el-button type="primary" size="small" @click="startBatchTranscribe" :disabled="batchTranscribing" :loading="batchTranscribing">
            🚀 开始批量转写
          </el-button>
        </div>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>
      <div v-if="batchError" class="error-msg">{{ batchError }}</div>
    </div>

    <!-- ====== 方式二：浏览器录音（支持多段） ====== -->
    <div class="section-title" style="margin-top:32px;">🎤 浏览器录音</div>
    <div class="record-zone" v-if="browserSupport">
      <!-- 录音中 -->
      <div v-if="recordState === 'recording' || recordState === 'paused'" class="record-active" style="margin-bottom:16px;">
        <div class="record-indicator">
          <span class="record-dot" :class="{ blink: recordState === 'recording' }"></span>
          <span class="record-timer">{{ formatDuration(activeRecordDuration) }}</span>
          <span class="record-limit">/ 60:00</span>
        </div>
        <div class="record-wave" v-if="recordState === 'recording'">
          <span v-for="i in 40" :key="i" class="wave-bar" :style="{ height: waveLevels[i-1] + 'px' }"></span>
        </div>
        <div class="record-actions">
          <el-button v-if="recordState === 'recording'" @click="pauseRecording">⏸ 暂停</el-button>
          <el-button v-if="recordState === 'paused'" @click="resumeRecording">▶ 继续</el-button>
          <el-button type="danger" @click="stopRecording">⏹ 停止</el-button>
        </div>
      </div>

      <!-- 空闲状态 + 设备选择 + 开始按钮 -->
      <div v-if="recordState === 'idle'" class="record-prompt" style="margin-bottom:16px;">
        <div class="device-selector">
          <label>选择麦克风：</label>
          <el-select v-model="selectedDeviceId" placeholder="-- 默认设备 --" style="flex: 1">
            <el-option v-for="d in audioDevices" :key="d.deviceId" :value="d.deviceId" :label="d.label || '麦克风'" />
          </el-select>
          <el-button size="small" @click="loadAudioDevices">刷新</el-button>
        </div>
        <div v-if="recordError" class="error-msg" style="margin-bottom:12px;">{{ recordError }}</div>
        <el-button type="danger" size="large" @click="startRecording">🎤 开始录音</el-button>
        <p style="margin-top:8px;color:#94a3b8;font-size:0.8rem;">最长 60 分钟，可连续录制多段</p>
      </div>

      <!-- 录音列表 -->
      <div v-if="recordings.length > 0" class="recordings-list">
        <div class="file-list-header">
          <span class="file-count">已录制 {{ recordings.length }} 段</span>
          <el-button v-if="recordingsUploadedCount > 0" type="primary" size="small" @click="batchTranscribeRecordings">
            📝 批量转写（{{ recordingsUploadedCount }} 段）
          </el-button>
        </div>
        <div class="file-list">
          <div v-for="(r, idx) in recordings" :key="r.id" class="file-row">
            <span class="file-order">{{ idx + 1 }}</span>
            <span class="record-name-col">
              <el-input v-model="r.name" placeholder="输入录音名称" size="small" :disabled="r.state === 'transcribing' || r.state === 'transcribe-done'" />
            </span>
            <span class="file-size">{{ formatDuration(r.duration) }}</span>
            <span class="file-format">{{ stateLabel(r.state) }}</span>
            <div class="file-actions">
              <!-- 待上传 -->
              <template v-if="r.state === 'done'">
                <el-button size="small" type="primary" @click="uploadRecordingFile(r)" :disabled="r.uploading" :loading="r.uploading">
                  {{ r.uploading ? '上传中...' : '📤 上传' }}
                </el-button>
                <el-button size="small" @click="removeRecording(idx)" title="删除">✕</el-button>
              </template>
              <!-- 已上传，待转写 -->
              <template v-if="r.state === 'uploaded'">
                <el-button size="small" type="primary" @click="startTranscribe(r)">📝 转写</el-button>
                <el-button size="small" @click="removeRecording(idx)" title="删除">✕</el-button>
              </template>
              <!-- 上传中 -->
              <template v-if="r.state === 'uploading'">
                <span class="batch-task-status">上传中...</span>
              </template>
              <!-- 转写中 -->
              <template v-if="r.state === 'transcribing'">
                <div class="batch-progress-bar" style="width:120px;">
                  <div class="progress-fill" :style="{ width: (r.taskProgress * 100) + '%' }"></div>
                </div>
                <span class="batch-task-status" style="margin-left:4px;">{{ progressLabel(r.taskProgress) }}</span>
              </template>
              <!-- 转写完成 -->
              <template v-if="r.state === 'transcribe-done'">
                <router-link :to="`/task/${r.taskId}`"><el-button size="small" type="primary">查看结果 →</el-button></router-link>
                <router-link :to="`/minutes/new?task_id=${r.taskId}`"><el-button size="small" type="success">📝 纪要</el-button></router-link>
                <el-button size="small" @click="removeRecording(idx)" title="删除">✕</el-button>
              </template>
              <!-- 错误 -->
              <template v-if="r.state === 'error'">
                <span class="failed-text" style="font-size:0.78rem;">❌ {{ r.error }}</span>
                <el-button size="small" @click="retryRecording(idx)">重试</el-button>
                <el-button size="small" @click="removeRecording(idx)" title="删除">✕</el-button>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 浏览器不支持录音 -->
    <div v-else class="record-zone unsupported">
      <p>⚠️ 当前浏览器不支持录音功能，请使用 Chrome/Edge/Firefox</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { uploadAudio, uploadRecording, submitTask, getTask, listMeetings } from '../api.js'
import CreateMeetingModal from '../components/CreateMeetingModal.vue'

// ====== 文件上传相关（支持多文件） ======
const fileInput = ref(null)
const dragging = ref(false)
const uploading = ref(false)
const uploadStatusText = ref('')
const uploadedFiles = ref([])  // 已上传的文件列表
const error = ref('')
const meetings = ref([])
const selectedMeetingId = ref('')
const selectedMeetingName = computed(() => {
  const m = meetings.value.find(m => m.id === selectedMeetingId.value)
  return m ? m.title : ''
})
const showNewMeeting = ref(false)

// 批量转写相关
const batchTranscribing = ref(false)
const batchTasks = ref([])  // { task_id, name, status, progress, statusText }
const batchAllDone = ref(false)
const batchPollingCount = ref(0)
const batchError = ref('')
let batchTimer = null

async function onMeetingCreated(m) {
  meetings.value = (await listMeetings()).records || []
  selectedMeetingId.value = m.id
  showNewMeeting.value = false
}

const batchDoneCount = computed(() => {
  return batchTasks.value.filter(t => t.status === 'completed').length
})

function onDrop(e) {
  dragging.value = false
  const files = e.dataTransfer.files
  if (files.length > 0) addFiles(files)
}

onMounted(async () => {
  try { meetings.value = (await listMeetings()).records || [] } catch (e) { /* ignore */ }
  setTimeout(() => loadAudioDevices(), 500)
})

function onFileSelect(e) {
  const files = e.target.files
  if (files.length > 0) addFiles(files)
  e.target.value = ''  // 允许重复选择同一文件
}

function addFiles(fileList) {
  error.value = ''
  const allowed = ['mp3', 'wav', 'm4a']
  const files = []
  for (const file of fileList) {
    const ext = file.name.split('.').pop().toLowerCase()
    if (!allowed.includes(ext)) {
      error.value = `不支持的格式: .${ext}，允许: ${allowed.join(', ')}`
      continue
    }
    if (file.size > 200 * 1024 * 1024) {
      error.value = `文件过大（${file.name}），限制 200MB`
      continue
    }
    files.push(file)
  }
  if (files.length > 0) uploadFiles(files)
}

async function uploadFiles(files) {
  uploading.value = true
  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    uploadStatusText.value = `上传中...(${i + 1}/${files.length}) ${file.name}`
    try {
      const result = await uploadAudio(file)
      uploadedFiles.value.push(result)
    } catch (e) {
      error.value = `上传失败（${file.name}）: ${e.message}`
    }
  }
  uploading.value = false
  uploadStatusText.value = ''
}

// 排序
const draggingIdx = ref(-1)
const dragOverIdx = ref(-1)

function onDragStart(idx, e) {
  draggingIdx.value = idx
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', String(idx))
}

function onDragOver(idx) {
  dragOverIdx.value = idx
}

function onDragLeave(idx) {
  if (dragOverIdx.value === idx) {
    dragOverIdx.value = -1
  }
}

function onDropFile(idx) {
  dragOverIdx.value = -1
  const fromIdx = draggingIdx.value
  draggingIdx.value = -1
  if (fromIdx === idx || fromIdx < 0) return
  const arr = [...uploadedFiles.value]
  const [moved] = arr.splice(fromIdx, 1)
  arr.splice(idx, 0, moved)
  uploadedFiles.value = arr
}

function onDragEnd() {
  draggingIdx.value = -1
  dragOverIdx.value = -1
}

function moveUp(idx) {
  if (idx <= 0) return
  const arr = uploadedFiles.value
  const tmp = arr[idx - 1]
  arr[idx - 1] = arr[idx]
  arr[idx] = tmp
  uploadedFiles.value = [...arr]  // trigger reactivity
}

function moveDown(idx) {
  if (idx >= uploadedFiles.value.length - 1) return
  const arr = uploadedFiles.value
  const tmp = arr[idx + 1]
  arr[idx + 1] = arr[idx]
  arr[idx] = tmp
  uploadedFiles.value = [...arr]
}

function removeFile(idx) {
  const arr = [...uploadedFiles.value]
  arr.splice(idx, 1)
  uploadedFiles.value = arr
  if (arr.length === 0) resetUpload()
}

// 批量转写（合并为单任务）
async function startBatchTranscribe() {
  if (uploadedFiles.value.length === 0) return
  batchTranscribing.value = true
  batchError.value = ''
  batchTasks.value = []
  batchAllDone.value = false
  batchPollingCount.value = 0

  try {
    const paths = uploadedFiles.value.map(f => f.path)
    const names = uploadedFiles.value.map(f => f.filename)
    const taskName = names.length === 1 ? names[0] : (names[0] + ` 等${names.length}个文件`)
    const taskParams = { audio_paths: paths }
    if (selectedMeetingId.value) taskParams.meeting_id = selectedMeetingId.value
    const result = await submitTask('asr', taskParams, taskName)
    batchTasks.value.push({
      task_id: result.task_id,
      name: taskName,
      status: result.status === 'completed' ? 'completed' : 'pending',
      progress: 0,
      statusText: result.status === 'completed' ? '已完成' : '排队中',
    })
    // 开始轮询
    startBatchPolling()
  } catch (e) {
    batchError.value = '提交失败: ' + (e.message || '未知错误')
    batchTranscribing.value = false
  }
}

function startBatchPolling() {
  batchPollingCount.value = 0
  pollBatchTasks()
  batchTimer = setInterval(() => {
    batchPollingCount.value += 2
    pollBatchTasks()
  }, 2000)
}

async function pollBatchTasks() {
  let allDone = true
  for (const bt of batchTasks.value) {
    if (bt.status === 'completed' || bt.status === 'failed') continue
    allDone = false
    try {
      const t = await getTask(bt.task_id)
      bt.status = t.status
      bt.progress = t.progress || 0
      if (t.status === 'completed') {
        bt.statusText = '✅ 已完成'
        bt.progress = 1.0
      } else if (t.status === 'failed') {
        bt.statusText = '❌ 失败'
        bt.error = t.error_message || ''
      } else if (t.status === 'processing') {
        bt.statusText = `转写中 ${Math.round((t.progress || 0) * 100)}%`
      } else {
        bt.statusText = '排队中'
      }
    } catch (e) { /* ignore */ }
  }
  if (allDone) {
    stopBatchPolling()
    batchAllDone.value = true
    batchTranscribing.value = false
  }
}

function stopBatchPolling() {
  if (batchTimer) {
    clearInterval(batchTimer)
    batchTimer = null
  }
}

function taskIcon(status) {
  if (status === 'completed') return '✅'
  if (status === 'failed') return '❌'
  if (status === 'processing') return '🔄'
  return '⏳'
}

function formatDuration(s) {
  if (typeof s !== 'number' || !isFinite(s)) return '00:00'
  const m = Math.floor(s / 60)
  const sec = s % 60
  if (m >= 60) {
    const h = Math.floor(m / 60)
    return `${h}时${m % 60}分${sec}秒`
  }
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function progressLabel(p) {
  if (p < 0.08) return '排队等待中...'
  if (p < 0.18) return '加载模型中...'
  if (p < 0.85) return `转写中...已完成 ${Math.round(p * 100)}%`
  if (p < 0.95) return '保存结果...'
  return '即将完成...'
}

function resetUpload() {
  uploadedFiles.value = []
  batchTasks.value = []
  batchTranscribing.value = false
  batchAllDone.value = false
  batchError.value = ''
  stopBatchPolling()
}

// ====== 录音相关（支持多段录制） ======
const recordingsUploadedCount = computed(() => {
  return recordings.value.filter(r => r.state === 'uploaded').length
})

async function batchTranscribeRecordings() {
  const uploaded = recordings.value.filter(r => r.state === 'uploaded')
  if (uploaded.length === 0) return
  try {
    await ElMessageBox.confirm(
      `确定批量转写 ${uploaded.length} 段录音？将合并为一份转写结果。`,
      '批量转写',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )
  } catch (e) {
    return  // 用户取消
  }

  const paths = uploaded.map(r => r.uploadPath)
  const names = uploaded.map(r => r.name)
  const taskName = names[0] + ` 等${names.length}个录音`

  // 标记所有录音为转写中
  for (const r of uploaded) {
    r.state = 'transcribing'
    r.taskProgress = 0
  }

  try {
    const taskParams = { audio_paths: paths }
    if (selectedMeetingId.value) taskParams.meeting_id = selectedMeetingId.value
    const result = await submitTask('asr', taskParams, taskName)
    const taskId = result.task_id
    // 所有录音共用一个 taskId
    for (const r of uploaded) {
      r.taskId = taskId
    }
    // 轮询转写进度
    const poll = setInterval(async () => {
      try {
        const t = await getTask(taskId)
        if (t.status === 'completed') {
          clearInterval(poll)
          for (const r of uploaded) {
            r.state = 'transcribe-done'
            r.taskProgress = 1.0
          }
        } else if (t.status === 'failed') {
          clearInterval(poll)
          for (const r of uploaded) {
            r.state = 'error'
            r.error = t.error_message || '转写失败'
          }
        } else if (t.status === 'processing') {
          for (const r of uploaded) {
            r.taskProgress = t.progress || 0
          }
        }
      } catch { /* ignore */ }
    }, 2000)
  } catch (e) {
    for (const r of uploaded) {
      r.state = 'error'
      r.error = '启动转写失败: ' + (e.message || '未知错误')
    }
  }
}
const MAX_RECORD_SECONDS = 3600  // 60 分钟
const browserSupport = ref(!!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia))
const waveLevels = ref(new Array(40).fill(2))
const audioDevices = ref([])
const selectedDeviceId = ref("")

const recordState = ref('idle')  // idle | recording | paused
const recordError = ref('')  // 当前录音错误提示
const recordings = ref([])  // { id, name, blob, duration, state, uploading, uploadPath, taskId, taskProgress, error }

// 当前录制会话临时变量（一次只录一段）
let activeRecordChunks = []
let activeRecordDuration = 0
let activeMediaRecorder = null
let activeMediaStream = null
let activeRecordTimer = null
let activeWaveTimer = null
let activeAudioContext = null
let activeAnalyserNode = null
let recIdCounter = 0

function updateWave() {
  if (!activeAnalyserNode) return
  try {
    const data = new Uint8Array(activeAnalyserNode.frequencyBinCount)
    activeAnalyserNode.getByteFrequencyData(data)
    const levels = []
    for (let i = 0; i < 40; i++) {
      levels.push(Math.max(2, Math.round((data[i] || 0) / 255 * 36)))
    }
    waveLevels.value = levels
  } catch (e) { /* ignore */ }
}

async function loadAudioDevices() {
  try {
    const s = await navigator.mediaDevices.getUserMedia({ audio: true })
    s.getTracks().forEach(t => t.stop())
    const devices = await navigator.mediaDevices.enumerateDevices()
    audioDevices.value = devices.filter(d => d.kind === 'audioinput')
    // 自动选择：优先选带"默认"的麦克风，否则选第一个非立体声混音的
    let mic = audioDevices.value.find(d => d.label.includes('默认') && !d.label.includes('立体声'))
    if (!mic) {
      mic = audioDevices.value.find(d => !d.label.includes('立体声') && !d.label.includes('混音'))
    }
    if (mic) {
      selectedDeviceId.value = mic.deviceId
    }
  } catch (e) { /* ignore */ }
}

async function startRecording() {
  activeRecordChunks = []
  activeRecordDuration = 0
  recordError.value = ''

  try {
    const constraints = { audio: true }
    if (selectedDeviceId.value) {
      constraints.audio = { deviceId: { exact: selectedDeviceId.value } }
    }
    const stream = await navigator.mediaDevices.getUserMedia(constraints)

    // 创建音频分析器用于波形显示
    try {
      activeAudioContext = new AudioContext()
      if (activeAudioContext.state === 'suspended') await activeAudioContext.resume()
      const source = activeAudioContext.createMediaStreamSource(stream)
      activeAnalyserNode = activeAudioContext.createAnalyser()
      activeAnalyserNode.fftSize = 64
      source.connect(activeAnalyserNode)
    } catch (e) { /* 波形非必须 */ }

    activeMediaRecorder = new MediaRecorder(stream)

    activeMediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        activeRecordChunks.push(e.data)
      }
    }

    activeMediaRecorder.onstop = () => {
      if (activeRecordChunks.length > 0) {
        const blob = new Blob(activeRecordChunks, { type: activeMediaRecorder.mimeType })
        recordings.value.push({
          id: ++recIdCounter,
          name: '录音_' + new Date().toLocaleString('zh-CN'),
          blob,
          duration: activeRecordDuration,
          state: 'done',
          uploading: false,
          uploadPath: null,
          taskId: null,
          taskProgress: 0,
          error: '',
        })
      }
      recordState.value = 'idle'
      releaseMic()
    }

    activeMediaRecorder.start()
    recordState.value = 'recording'
    activeMediaStream = stream

    // 计时器
    activeRecordTimer = setInterval(() => {
      activeRecordDuration++
      if (activeRecordDuration >= MAX_RECORD_SECONDS) {
        stopRecording()
      }
    }, 1000)

    // 波形更新（高频，让波浪动起来）
    updateWave()
    activeWaveTimer = setInterval(updateWave, 150)
  } catch (e) {
    if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
      recordError.value = '❌ 麦克风权限被拒绝，请在浏览器设置中允许麦克风访问'
    } else if (e.name === 'NotFoundError') {
      recordError.value = '❌ 未检测到麦克风设备'
    } else {
      recordError.value = '❌ 启动录音失败: ' + (e.message || '未知错误')
    }
    recordState.value = 'idle'
  }
}

function pauseRecording() {
  if (activeMediaRecorder && activeMediaRecorder.state === 'recording') {
    activeMediaRecorder.pause()
    recordState.value = 'paused'
    if (activeRecordTimer) clearInterval(activeRecordTimer)
    if (activeWaveTimer) clearInterval(activeWaveTimer)
  }
}

function resumeRecording() {
  if (activeMediaRecorder && activeMediaRecorder.state === 'paused') {
    activeMediaRecorder.resume()
    recordState.value = 'recording'
    activeRecordTimer = setInterval(() => {
      activeRecordDuration++
      if (activeRecordDuration >= MAX_RECORD_SECONDS) {
        stopRecording()
      }
    }, 1000)
    activeWaveTimer = setInterval(updateWave, 150)
  }
}

function stopRecording() {
  if (activeRecordTimer) { clearInterval(activeRecordTimer); activeRecordTimer = null }
  if (activeWaveTimer) { clearInterval(activeWaveTimer); activeWaveTimer = null }
  if (activeMediaRecorder && activeMediaRecorder.state !== 'inactive') {
    activeMediaRecorder.stop()
  }
}

function releaseMic() {
  if (activeMediaStream) {
    activeMediaStream.getTracks().forEach(t => t.stop())
    activeMediaStream = null
  }
  if (activeAudioContext) {
    activeAudioContext.close().catch(() => {})
    activeAudioContext = null
    activeAnalyserNode = null
  }
}

// 第一步：上传录音文件到服务器
async function uploadRecordingFile(r) {
  if (!r.blob) return
  const name = r.name.trim() || ('录音_' + new Date().toLocaleString('zh-CN'))
  const ext = r.blob.type.includes('mp4') ? 'm4a' : 'webm'
  r.uploading = true
  r.state = 'uploading'
  try {
    const result = await uploadRecording(r.blob, name + '.' + ext)
    r.uploadPath = result.path
    r.state = 'uploaded'
  } catch (e) {
    r.state = 'error'
    r.error = '上传失败: ' + (e.message || '未知错误')
  } finally {
    r.uploading = false
  }
}

// 第二步：转写（需二次确认）
async function startTranscribe(r) {
  if (!r.uploadPath) return
  try {
    await ElMessageBox.confirm(
      `确定开始转写「${r.name}」？`,
      '启动转写',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'info' }
    )
  } catch (e) {
    return  // 用户取消
  }

  r.state = 'transcribing'
  r.taskProgress = 0
  try {
    const taskParams = { audio_path: r.uploadPath }
    if (selectedMeetingId.value) taskParams.meeting_id = selectedMeetingId.value
    const taskResult = await submitTask('asr', taskParams, r.name)
    r.taskId = taskResult.task_id
    // 轮询转写进度
    const poll = setInterval(async () => {
      try {
        const t = await getTask(taskResult.task_id)
        if (t.status === 'completed') {
          clearInterval(poll)
          r.state = 'transcribe-done'
          r.taskProgress = 1.0
        } else if (t.status === 'failed') {
          clearInterval(poll)
          r.state = 'error'
          r.error = t.error_message || '转写失败'
        } else if (t.status === 'processing') {
          r.taskProgress = t.progress || 0
        }
      } catch (e) { /* ignore */ }
    }, 2000)
  } catch (e) {
    r.state = 'error'
    r.error = '启动转写失败: ' + (e.message || '未知错误')
  }
}

function removeRecording(idx) {
  recordings.value.splice(idx, 1)
}

function retryRecording(idx) {
  const r = recordings.value[idx]
  r.state = r.uploadPath ? 'uploaded' : 'done'
  r.error = ''
  r.taskId = null
  r.taskProgress = 0
  r.uploading = false
}

function stateLabel(s) {
  const map = {
    done: '待上传',
    uploading: '上传中',
    uploaded: '待转写',
    transcribing: '转写中',
    'transcribe-done': '✅ 完成',
    error: '❌ 失败',
  }
  return map[s] || s
}

onUnmounted(() => {
  stopBatchPolling()
  if (activeRecordTimer) clearInterval(activeRecordTimer)
  if (activeWaveTimer) clearInterval(activeWaveTimer)
  if (activeMediaRecorder && activeMediaRecorder.state !== 'inactive') {
    activeMediaRecorder.stop()
  }
  releaseMic()
})
</script>

<style scoped>
.upload-page { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.8rem; margin: 0; }

.section-title { font-size: 0.95rem; color: #1e293b; font-weight: 600; margin-bottom: 12px; padding-bottom: 8px; border-bottom: 1px solid #e2e8f0; }

/* 会议选择 */
.meeting-selector { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.meeting-selector label { font-size: 0.85rem; color: #64748b; font-weight: 500; white-space: nowrap; }

/* 上传区域 */
.upload-zone { border: 2px dashed #e2e8f0; border-radius: 12px; padding: 40px; text-align: center; transition: all 0.2s; }
.upload-zone.dragging { border-color: #4f46e5; background: #eef2ff; }
.upload-zone.uploaded { border-style: solid; border-color: #16a34a; padding: 24px; }
.upload-prompt { color: #94a3b8; }
.upload-icon { font-size: 2.5rem; margin-bottom: 8px; }
.upload-progress { padding: 20px; }
.spinner { width: 32px; height: 32px; border: 3px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 12px; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinner-sm { display: inline-block; width: 14px; height: 14px; border: 2px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 4px; }
.upload-success { }
.meeting-tag { font-size: 0.8rem; color: #4f46e5; background: #eef2ff; padding: 4px 10px; border-radius: 4px; display: inline-block; margin-bottom: 8px; }
.file-info { display: flex; gap: 16px; justify-content: center; font-size: 0.82rem; color: #64748b; margin-bottom: 16px; }
.action-row { display: flex; gap: 8px; justify-content: center; }
.btn-primary, .btn-minutes { padding: 10px 24px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.88rem; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; }
.btn-primary:hover, .btn-minutes:hover { background: #4338ca; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { padding: 10px 24px; border: 1px solid #e2e8f0; background: #fff; border-radius: 8px; cursor: pointer; font-size: 0.88rem; color: #64748b; }
.btn-secondary:hover { border-color: #dc2626; color: #dc2626; }
.btn-sm { padding: 6px 14px; font-size: 0.82rem; }
.task-progress { margin-top: 12px; }
.progress-section { max-width: 400px; margin: 0 auto; }
.progress-bar { height: 8px; background: #e2e8f0; border-radius: 4px; overflow: hidden; }
.progress-fill { height: 100%; background: #4f46e5; border-radius: 4px; transition: width 0.3s; }
.progress-text { font-size: 0.82rem; color: #64748b; margin-top: 6px; }
.polling-hint { font-size: 0.78rem; color: #94a3b8; margin-top: 8px; }
.task-actions { display: flex; gap: 8px; justify-content: center; margin-top: 12px; }
.failed-text { color: #dc2626; font-weight: 500; }
.error-detail { font-size: 0.82rem; color: #dc2626; margin-top: 4px; }
.error-msg { color: #dc2626; font-size: 0.85rem; margin-top: 10px; padding: 8px 12px; background: #fef2f2; border-radius: 6px; }

/* 录音区域 */
.record-zone { border: 2px dashed #e2e8f0; border-radius: 12px; padding: 40px; text-align: center; }
.record-zone.unsupported { padding: 24px; color: #94a3b8; font-size: 0.85rem; }
.record-prompt { color: #94a3b8; }
.record-icon { font-size: 2.5rem; margin-bottom: 8px; }
.device-selector { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 0.85rem; }
.device-selector label { color: #64748b; white-space: nowrap; }
.btn-record-start { padding: 12px 32px; background: #dc2626; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 1rem; margin-top: 12px; transition: background 0.2s; }
.btn-record-start:hover { background: #b91c1c; }

.record-active { }
.record-indicator { display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 16px; }
.record-dot { width: 12px; height: 12px; border-radius: 50%; background: #dc2626; display: inline-block; }
.record-dot.blink { animation: blink 1s infinite; }
@keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.2; } }
.record-timer { font-size: 2rem; font-weight: 700; color: #1e293b; font-variant-numeric: tabular-nums; }
.record-limit { font-size: 0.85rem; color: #94a3b8; }

.record-wave { display: flex; align-items: center; justify-content: center; gap: 2px; height: 40px; margin-bottom: 16px; }
.wave-bar { width: 4px; border-radius: 2px; background: #4f46e5; transition: height 0.1s; min-height: 2px; }

.record-actions { display: flex; gap: 8px; justify-content: center; }

.record-name-input { width: 100%; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 4px; font-size: 0.85rem; outline: none; box-sizing: border-box; }
.record-name-input:focus { border-color: #4f46e5; }
.record-name-col { flex: 1; min-width: 0; margin-right: 4px; }

.record-error { }

/* 多文件列表 */
.upload-zone.has-files { border-style: solid; border-color: #4f46e5; padding: 20px; text-align: left; }
.file-list-wrap { }
.file-list-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.file-count { font-size: 0.85rem; color: #64748b; font-weight: 500; }
.meeting-tag-mini { font-size: 0.78rem; color: #4f46e5; background: #eef2ff; padding: 3px 8px; border-radius: 4px; }

.file-list { max-height: 360px; overflow-y: auto; }
.file-row { display: flex; align-items: center; gap: 8px; padding: 10px 12px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 6px; background: #fff; transition: all 0.15s; cursor: default; }
.file-row:hover { background: #f8fafc; }
.file-row.dragging-src { opacity: 0.4; }
.file-row.drag-over { border-color: #4f46e5; background: #eef2ff; transform: scale(1.02); box-shadow: 0 2px 8px rgba(79,70,229,0.15); }
.drag-handle { cursor: grab; color: #cbd5e1; font-size: 1rem; line-height: 1; user-select: none; flex-shrink: 0; padding: 0 2px; }
.drag-handle:hover { color: #4f46e5; }
.file-row:hover .drag-handle { color: #94a3b8; }
.file-order { width: 24px; height: 24px; border-radius: 50%; background: #4f46e5; color: #fff; font-size: 0.75rem; font-weight: 600; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.file-name { flex: 1; font-size: 0.85rem; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { font-size: 0.78rem; color: #94a3b8; width: 60px; text-align: right; flex-shrink: 0; }
.file-format { font-size: 0.75rem; color: #4f46e5; background: #eef2ff; padding: 2px 6px; border-radius: 4px; width: 36px; text-align: center; flex-shrink: 0; }

.file-list-actions { display: flex; gap: 8px; justify-content: center; margin-top: 16px; }

/* 批量转写进度 */
.batch-progress { margin-top: 16px; text-align: left; }
.batch-progress-header { font-size: 0.85rem; color: #64748b; margin-bottom: 10px; }
.batch-task-list { max-height: 300px; overflow-y: auto; }
.batch-task-row { display: flex; align-items: center; gap: 8px; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; margin-bottom: 4px; background: #fff; }
.batch-task-icon { font-size: 1rem; flex-shrink: 0; }
.batch-task-name { flex: 1; font-size: 0.82rem; color: #1e293b; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.batch-task-status { font-size: 0.78rem; color: #94a3b8; flex-shrink: 0; min-width: 80px; text-align: right; }
.batch-progress-bar { width: 80px; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; flex-shrink: 0; }
.batch-progress-bar .progress-fill { height: 100%; background: #4f46e5; border-radius: 2px; transition: width 0.3s; }

.batch-all-done { margin-top: 16px; text-align: center; }
.batch-all-done > p { font-size: 0.95rem; color: #16a34a; font-weight: 600; margin-bottom: 12px; }
.batch-task-link { margin-bottom: 6px; display: flex; gap: 6px; justify-content: center; }
</style>