<template>
  <div class="upload-page">
    <div class="page-header">
      <h1>音频转写</h1>
      <p>支持 mp3、wav、m4a 格式，最大 200MB；也可直接浏览器录音</p>
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
      <button class="btn-add-meeting" @click="showNewMeeting = true">+ 新增会议</button>
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
      :class="{ dragging, uploaded: !!uploadResult }"
      @dragover.prevent="dragging = true"
      @dragleave.prevent="dragging = false"
      @drop.prevent="onDrop"
    >
      <div v-if="!uploading && !uploadResult" class="upload-prompt">
        <div class="upload-icon">🎙️</div>
        <p>拖拽音频文件到此处，或点击选择</p>
        <input type="file" ref="fileInput" accept=".mp3,.wav,.m4a" @change="onFileSelect" hidden />
        <button class="btn-select" @click="$refs.fileInput.click()">选择文件</button>
      </div>

      <div v-if="uploading" class="upload-progress">
        <div class="spinner"></div>
        <p>上传中...</p>
      </div>

      <div v-if="uploadResult" class="upload-success">
        <div class="check-icon">✓</div>
        <p>上传成功</p>
        <div v-if="selectedMeetingId && selectedMeetingName" class="meeting-tag">
          📋 关联会议：{{ selectedMeetingName }}
        </div>
        <div class="file-info">
          <span>{{ uploadResult.filename }}</span>
          <span>{{ (uploadResult.size_bytes / 1024).toFixed(1) }} KB</span>
          <span>{{ uploadResult.format }}</span>
        </div>

        <template v-if="viewState === 'idle'">
          <div class="action-row">
            <button class="btn-primary" @click="startTranscribe" :disabled="transcribing">
              <span v-if="transcribing" class="spinner-sm"></span>
              {{ transcribing ? '提交中...' : '开始转写' }}
            </button>
            <button class="btn-secondary" @click="resetUpload">重新上传</button>
          </div>
        </template>

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
              {{ pollingCount > 0 ? `已等待 ${formatDuration(pollingCount)}` : '自动刷新中...' }}
            </p>
          </div>
        </template>

        <template v-if="viewState === 'done'">
          <div class="task-link">
            <p>✅ 转写完成</p>
            <div class="task-actions">
              <router-link :to="`/task/${taskId}`" class="btn-primary">查看转写结果 →</router-link>
              <router-link :to="`/minutes/new?task_id=${taskId}`" class="btn-minutes">📝 生成纪要</router-link>
            </div>
          </div>
        </template>

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

    <!-- ====== 方式二：浏览器录音 ====== -->
    <div class="section-title" style="margin-top:32px;">🎤 浏览器录音</div>
    <div class="record-zone" v-if="browserSupport">
      <div class="device-selector" v-if="recordState === 'idle'">
        <label>选择麦克风：</label>
        <select v-model="selectedDeviceId" class="device-select">
          <option value="">-- 默认设备 --</option>
          <option v-for="d in audioDevices" :key="d.deviceId" :value="d.deviceId">{{ d.label || "麦克风" }}</option>
        </select>
        <button class="btn-refresh-devices" @click="loadAudioDevices">刷新</button>
      </div>
      <!-- 空闲状态 -->
      <div v-if="recordState === 'idle'" class="record-prompt">
        <div class="record-icon">🎤</div>
        <p>点击下方按钮开始录音，最长 30 分钟</p>
        <button class="btn-record-start" @click="startRecording">🎤 开始录音</button>
      </div>

      <!-- 录音中 -->
      <div v-if="recordState === 'recording' || recordState === 'paused'" class="record-active">
        <div class="record-indicator">
          <span class="record-dot" :class="{ blink: recordState === 'recording' }"></span>
          <span class="record-timer">{{ formatDuration(recordDuration) }}</span>
          <span class="record-limit">/ 30:00</span>
        </div>
        <div class="record-wave" v-if="recordState === 'recording'">
          <span v-for="i in 40" :key="i" class="wave-bar" :style="{ height: waveLevels[i-1] + 'px' }"></span>
        </div>
        
        <div class="record-actions">
          <button v-if="recordState === 'recording'" class="btn-record-pause" @click="pauseRecording">⏸ 暂停</button>
          <button v-if="recordState === 'paused'" class="btn-record-resume" @click="resumeRecording">▶ 继续</button>
          <button class="btn-record-stop" @click="stopRecording">⏹ 停止</button>
        </div>
        <div class="record-hint">录音完成后，可输入名称并自动上传转写</div>
      </div>

      <!-- 录音完成 → 命名确认 -->
      <div v-if="recordState === 'done'" class="record-done">
        <div class="check-icon">✓</div>
        <p class="record-done-text">录音完成：{{ formatDuration(recordDuration) }}</p>
        <div class="record-name-row">
          <input v-model="recordName" class="record-name-input" placeholder="输入录音名称，如：MOPRO-1890 评审会议" />
        </div>
        <div class="record-done-actions">
          <button class="btn-primary" @click="confirmUpload" :disabled="recordUploading">
            <span v-if="recordUploading" class="spinner-sm"></span>
            {{ recordUploading ? '上传中...' : '✅ 确认上传并转写' }}
          </button>
          <button class="btn-secondary" @click="cancelRecording">重新录制</button>
        </div>
      </div>

      <!-- 录音上传中/转写中 -->
      <div v-if="recordState === 'uploading'" class="record-progress">
        <div class="spinner"></div>
        <p>上传录音中...</p>
      </div>
      <div v-if="recordState === 'transcribing'" class="record-progress">
        <div class="progress-section">
          <div class="progress-bar">
            <div class="progress-fill" :style="{ width: (taskProgress * 100) + '%' }"></div>
          </div>
          <div class="progress-text">{{ progressLabel(taskProgress) }}</div>
        </div>
        <p class="polling-hint">
          <span class="spinner-sm"></span>
          {{ pollingCount > 0 ? `已等待 ${formatDuration(pollingCount)}` : '自动转写中...' }}
        </p>
      </div>
      <div v-if="recordState === 'transcribe-done'" class="record-result">
        <p>✅ 转写完成</p>
        <div class="task-actions">
          <router-link :to="`/task/${taskId}`" class="btn-primary">查看转写结果 →</router-link>
          <router-link :to="`/minutes/new?task_id=${taskId}`" class="btn-minutes">📝 生成纪要</router-link>
        </div>
      </div>
      <div v-if="recordState === 'error'" class="record-error">
        <p class="failed-text">❌ {{ recordError }}</p>
        <button class="btn-secondary" @click="resetRecord">重新录制</button>
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

// ====== 文件上传相关 ======
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
const showNewMeeting = ref(false)

async function onMeetingCreated(m) {
  meetings.value = await listMeetings()
  selectedMeetingId.value = m.id
  showNewMeeting.value = false
}
let timer = null

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
  setTimeout(() => loadAudioDevices(), 500)
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
    const taskParams = { audio_path: uploadResult.value.path }
    if (selectedMeetingId.value) taskParams.meeting_id = selectedMeetingId.value
    const result = await submitTask('asr', taskParams, uploadResult.value.filename)
    taskId.value = result.task_id
    taskStatus.value = 'pending'
    taskProgress.value = 0
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
  } catch { /* ignore */ }
}

function stopPolling() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
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
  stopPolling()
  uploadResult.value = null
  taskId.value = null
  taskStatus.value = ''
  taskProgress.value = 0
  taskError.value = ''
  error.value = ''
}

// ====== 录音相关 ======
const MAX_RECORD_SECONDS = 1800  // 30 分钟
const browserSupport = ref(!!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia))
const audioDevices = ref([])
const waveLevels = ref(new Array(40).fill(2))
const selectedDeviceId = ref("")

const recordState = ref('idle')  // idle | recording | paused | done | uploading | transcribing | transcribe-done | error
const recordDuration = ref(0)
const recordChunks = ref([])
const recordName = ref('')
const recordError = ref('')
const recordUploading = ref(false)
let mediaRecorder = null
let mediaStream = null
let recordTimer = null
let audioContext = null
let analyserNode = null

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
  } catch { /* ignore */ }
}

async function startRecording() {
  recordError.value = ''
  recordName.value = ''
  recordChunks.value = []
  recordDuration.value = 0

  try {
    const constraints = { audio: true }
    if (selectedDeviceId.value) {
      constraints.audio = { deviceId: { exact: selectedDeviceId.value } }
    }
    const stream = await navigator.mediaDevices.getUserMedia(constraints)

    // 创建音频分析器用于波形显示
    try {
      audioContext = new AudioContext()
      if (audioContext.state === 'suspended') await audioContext.resume()
      const source = audioContext.createMediaStreamSource(stream)
      analyserNode = audioContext.createAnalyser()
      analyserNode.fftSize = 64
      source.connect(analyserNode)
    } catch { /* 波形非必须 */ }

    // 使用 MediaRecorder
    mediaRecorder = new MediaRecorder(stream)

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) {
        recordChunks.value.push(e.data)
      }
    }

    mediaRecorder.onstop = () => {
      if (recordChunks.value.length === 0) {
        recordError.value = '未捕获到音频数据'
        recordState.value = 'error'
      } else {
        const blob = new Blob(recordChunks.value, { type: mediaRecorder.mimeType })
        recordBlob.value = blob
        recordState.value = 'done'
      }
      releaseMic()
    }

    mediaRecorder.start()
    recordState.value = 'recording'
    mediaStream = stream

    // 计时器
    recordTimer = setInterval(() => {
      recordDuration.value++
      updateWave()
      if (recordDuration.value >= MAX_RECORD_SECONDS) {
        stopRecording()
      }
    }, 1000)
  } catch (e) {
    if (e.name === 'NotAllowedError' || e.name === 'PermissionDeniedError') {
      recordError.value = '麦克风权限被拒绝'
    } else if (e.name === 'NotFoundError') {
      recordError.value = '未检测到麦克风设备'
    } else {
      recordError.value = '启动录音失败: ' + e.message
    }
    recordState.value = 'error'
  }
}

function pauseRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.pause()
    recordState.value = 'paused'
    if (recordTimer) clearInterval(recordTimer)
  }
}

function updateWave() {
  if (!analyserNode) return
  try {
    const data = new Uint8Array(analyserNode.frequencyBinCount)
    analyserNode.getByteFrequencyData(data)
    const levels = []
    for (let i = 0; i < 40; i++) {
      levels.push(Math.max(2, Math.round((data[i] || 0) / 255 * 36)))
    }
    waveLevels.value = levels
  } catch { /* ignore */ }
}

function resumeRecording() {
  if (mediaRecorder && mediaRecorder.state === 'paused') {
    mediaRecorder.resume()
    recordState.value = 'recording'
    recordTimer = setInterval(() => {
      recordDuration.value++
      updateWave()
      if (recordDuration.value >= MAX_RECORD_SECONDS) {
        stopRecording()
      }
    }, 1000)
  }
}

function stopRecording() {
  if (recordTimer) { clearInterval(recordTimer); recordTimer = null }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
}

const recordBlob = ref(null)

function releaseMic() {
  if (mediaStream) {
    mediaStream.getTracks().forEach(t => t.stop())
    mediaStream = null
  }
  if (audioContext) {
    audioContext.close().catch(() => {})
    audioContext = null
    analyserNode = null
  }
}


async function confirmUpload() {
  if (!recordBlob.value) return
  const name = recordName.value.trim() || ('录音_' + new Date().toLocaleString('zh-CN'))
  const ext = recordBlob.value.type.includes('mp4') ? 'm4a' : 'webm'
  recordUploading.value = true
  try {
    const result = await uploadRecording(recordBlob.value, name + '.' + ext)
    recordState.value = 'transcribing'
    const taskParams = { audio_path: result.path }
    if (selectedMeetingId.value) taskParams.meeting_id = selectedMeetingId.value
    const taskResult = await submitTask('asr', taskParams, name)
    taskId.value = taskResult.task_id
    taskStatus.value = 'pending'
    taskProgress.value = 0
    startPolling()
    // 监听转写完成
    const waitForTranscribe = setInterval(async () => {
      try {
        const t = await getTask(taskResult.task_id)
        if (t.status === 'completed') {
          clearInterval(waitForTranscribe)
          taskStatus.value = 'completed'
          taskProgress.value = 1.0
          recordState.value = 'transcribe-done'
        } else if (t.status === 'failed') {
          clearInterval(waitForTranscribe)
          recordError.value = t.error_message || '转写失败'
          recordState.value = 'error'
        }
      } catch { /* ignore */ }
    }, 2000)
  } catch (e) {
    recordError.value = '上传失败: ' + e.message
    recordState.value = 'error'
  } finally {
    recordUploading.value = false
  }
}

function cancelRecording() {
  resetRecord()
}

function resetRecord() {
  if (recordTimer) { clearInterval(recordTimer); recordTimer = null }
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop()
  }
  releaseMic()
  recordState.value = 'idle'
  recordDuration.value = 0
  recordChunks.value = []
  recordName.value = ''
  recordBlob.value = null
  recordError.value = ''
  recordUploading.value = false
  waveLevels.value = new Array(40).fill(2)
  stopPolling()
}

onUnmounted(() => {
  stopPolling()
  resetRecord()
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
.meeting-select { flex: 1; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.85rem; outline: none; }
.meeting-select:focus { border-color: #4f46e5; }
.btn-add-meeting { padding: 8px 14px; border: 1px dashed #4f46e5; background: #fff; color: #4f46e5; border-radius: 6px; cursor: pointer; font-size: 0.82rem; white-space: nowrap; }
.btn-add-meeting:hover { background: #eef2ff; }

/* 上传区域 */
.upload-zone { border: 2px dashed #e2e8f0; border-radius: 12px; padding: 40px; text-align: center; transition: all 0.2s; }
.upload-zone.dragging { border-color: #4f46e5; background: #eef2ff; }
.upload-zone.uploaded { border-style: solid; border-color: #16a34a; padding: 24px; }
.upload-prompt { color: #94a3b8; }
.upload-icon { font-size: 2.5rem; margin-bottom: 8px; }
.btn-select { margin-top: 12px; padding: 10px 24px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.9rem; }
.btn-select:hover { background: #4338ca; }
.upload-progress { padding: 20px; }
.spinner { width: 32px; height: 32px; border: 3px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; margin: 0 auto 12px; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinner-sm { display: inline-block; width: 14px; height: 14px; border: 2px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; vertical-align: middle; margin-right: 4px; }
.upload-success { }
.check-icon { width: 48px; height: 48px; border-radius: 50%; background: #16a34a; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 1.4rem; margin: 0 auto 8px; font-weight: bold; }
.meeting-tag { font-size: 0.8rem; color: #4f46e5; background: #eef2ff; padding: 4px 10px; border-radius: 4px; display: inline-block; margin-bottom: 8px; }
.file-info { display: flex; gap: 16px; justify-content: center; font-size: 0.82rem; color: #64748b; margin-bottom: 16px; }
.action-row { display: flex; gap: 8px; justify-content: center; }
.btn-primary, .btn-minutes { padding: 10px 24px; background: #4f46e5; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.88rem; text-decoration: none; display: inline-flex; align-items: center; gap: 4px; }
.btn-primary:hover, .btn-minutes:hover { background: #4338ca; }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-secondary { padding: 10px 24px; border: 1px solid #e2e8f0; background: #fff; border-radius: 8px; cursor: pointer; font-size: 0.88rem; color: #64748b; }
.btn-secondary:hover { border-color: #dc2626; color: #dc2626; }
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
.device-selector { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 0.85rem; }
.device-selector label { color: #64748b; white-space: nowrap; }
.device-select { flex: 1; padding: 6px 10px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.85rem; outline: none; }
.device-select:focus { border-color: #4f46e5; }
.btn-refresh-devices { padding: 4px 10px; border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; cursor: pointer; font-size: 0.78rem; color: #64748b; }
.btn-refresh-devices:hover { border-color: #4f46e5; color: #4f46e5; }
.record-prompt { color: #94a3b8; }
.record-icon { font-size: 2.5rem; margin-bottom: 8px; }
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
.btn-record-pause, .btn-record-resume { padding: 10px 24px; border: 1px solid #e2e8f0; background: #fff; border-radius: 8px; cursor: pointer; font-size: 0.88rem; color: #64748b; }
.btn-record-pause:hover, .btn-record-resume:hover { border-color: #4f46e5; color: #4f46e5; }
.btn-record-stop { padding: 10px 24px; background: #dc2626; color: #fff; border: none; border-radius: 8px; cursor: pointer; font-size: 0.88rem; }
.btn-record-stop:hover { background: #b91c1c; }
.record-hint { font-size: 0.78rem; color: #94a3b8; margin-top: 12px; }

.record-done { }
.record-done-text { font-size: 0.9rem; color: #1e293b; margin: 8px 0 16px; }
.record-name-row { max-width: 400px; margin: 0 auto 16px; }
.record-name-input { width: 100%; padding: 10px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; box-sizing: border-box; }
.record-name-input:focus { border-color: #4f46e5; }
.record-done-actions { display: flex; gap: 8px; justify-content: center; }

.record-progress { padding: 20px; }
.record-result { }
.record-error { }
</style>