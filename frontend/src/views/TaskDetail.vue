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

        <!-- 进度条 -->
        <div v-if="task.status === 'processing'" class="progress-bar">
          <div class="progress-fill" :style="{ width: (task.progress * 100) + '%' }"></div>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="task.status === 'failed' && task.error_message" class="error-card">
        <h3>错误信息</h3>
        <pre>{{ task.error_message }}</pre>
      </div>

      <!-- 转写结果 -->
      <div v-if="task.status === 'completed' && task.result_summary" class="result-card">
        <h3>转写结果预览</h3>
        <div class="result-text">{{ task.result_summary }}</div>
        <div v-if="task.result_path" class="result-path">
          完整结果: {{ task.result_path }}
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
import { ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { getTask } from '../api.js'

const route = useRoute()
const task = ref(null)
const loading = ref(true)
const pollingCount = ref(0)
let timer = null

async function fetchTask() {
  try {
    task.value = await getTask(route.params.id)
    if (task.value.status === 'pending' || task.value.status === 'processing') {
      pollingCount.value++
    }
  } catch {
    task.value = null
  } finally {
    loading.value = false
  }
}

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
})

function statusLabel(s) {
  const map = { pending: '等待中', processing: '处理中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleString('zh-CN')
}
</script>

<style scoped>
.task-page {
  max-width: 640px;
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

.progress-bar {
  margin-top: 12px;
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