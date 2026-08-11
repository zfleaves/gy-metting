<template>
  <div class="upload-page">
    <div class="page-header">
      <h1>音频转写</h1>
      <p>支持 mp3、wav、m4a 格式，最大 200MB</p>
    </div>

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
        <div class="file-info">
          <span>{{ uploadResult.filename }}</span>
          <span>{{ (uploadResult.size_bytes / 1024).toFixed(1) }} KB</span>
          <span>{{ uploadResult.format }}</span>
        </div>

        <div v-if="!taskId" class="action-row">
          <button class="btn-primary" @click="startTranscribe" :disabled="transcribing">
            <span v-if="transcribing" class="spinner-sm"></span>
            {{ transcribing ? '提交中...' : '开始转写' }}
          </button>
          <button class="btn-secondary" @click="resetUpload">重新上传</button>
        </div>

        <div v-if="taskId" class="task-link">
          <p>任务已提交</p>
          <router-link :to="`/task/${taskId}`" class="btn-primary">查看转写结果 →</router-link>
        </div>
      </div>

      <div v-if="error" class="error-msg">{{ error }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { uploadAudio, submitTask } from '../api.js'

const fileInput = ref(null)
const dragging = ref(false)
const uploading = ref(false)
const transcribing = ref(false)
const uploadResult = ref(null)
const taskId = ref(null)
const error = ref('')

function onDrop(e) {
  dragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) processFile(file)
}

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
  try {
    const result = await submitTask('asr', { audio_path: uploadResult.value.path })
    taskId.value = result.task_id
  } catch (e) {
    error.value = '提交失败: ' + e.message
  } finally {
    transcribing.value = false
  }
}

function resetUpload() {
  uploadResult.value = null
  taskId.value = null
  error.value = ''
}
</script>

<style scoped>
.upload-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h1 {
  font-size: 1.3rem;
  margin: 0 0 4px;
  color: #1a1a2e;
}

.page-header p {
  color: #94a3b8;
  font-size: 0.9rem;
}

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

.upload-zone.dragging {
  border-color: #4f46e5;
  background: #eef2ff;
}

.upload-zone.uploaded {
  border-color: #22c55e;
  border-style: solid;
}

.upload-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}

.upload-prompt p {
  color: #64748b;
  margin-bottom: 16px;
}

.btn-select, .btn-primary, .btn-secondary {
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 0.95rem;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-select {
  background: #f1f5f9;
  color: #334155;
}

.btn-primary {
  background: #4f46e5;
  color: #fff;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  background: #fff;
  color: #64748b;
  border: 1px solid #e2e8f0;
}

.spinner, .spinner-sm {
  border: 3px solid #e2e8f0;
  border-top-color: #4f46e5;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.spinner { width: 36px; height: 36px; margin: 0 auto 12px; }
.spinner-sm { width: 16px; height: 16px; display: inline-block; margin-right: 6px; vertical-align: middle; }

@keyframes spin { to { transform: rotate(360deg); } }

.check-icon {
  width: 48px;
  height: 48px;
  background: #dcfce7;
  color: #16a34a;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
  margin: 0 auto 12px;
}

.file-info {
  display: flex;
  gap: 12px;
  margin: 12px 0;
  color: #64748b;
  font-size: 0.9rem;
}

.action-row {
  display: flex;
  gap: 12px;
  margin-top: 16px;
  justify-content: center;
}

.task-link {
  margin-top: 16px;
}

.task-link p {
  color: #64748b;
  margin-bottom: 8px;
}

.task-link .btn-primary {
  display: inline-block;
  text-decoration: none;
}

.error-msg {
  color: #dc2626;
  background: #fef2f2;
  padding: 8px 16px;
  border-radius: 6px;
  margin-top: 12px;
}
</style>