<template>
  <div class="home">
    <div class="hero">
      <h1>AI 智能会议纪要</h1>
      <p class="subtitle">上传音频 → 语音转写 → AI 生成纪要，一站式完成</p>
      <div class="actions">
        <router-link to="/upload" class="btn-primary">开始使用</router-link>
      </div>
    </div>

    <div class="status-bar">
      <div class="status-item">
        <span class="dot" :class="serverOk ? 'green' : 'red'"></span>
        服务状态: {{ serverOk ? '正常' : '离线' }}
      </div>
      <div class="status-item">版本: {{ version }}</div>
    </div>

    <div class="recent-tasks" v-if="tasks.length">
      <h2>最近任务</h2>
      <div class="task-list">
        <div
          v-for="task in tasks"
          :key="task.id"
          class="task-card"
          @click="$router.push(`/task/${task.id}`)"
        >
          <span class="task-type">{{ task.type }}</span>
          <span class="task-status" :class="task.status">{{ statusLabel(task.status) }}</span>
          <span class="task-time">{{ formatTime(task.created_at) }}</span>
          <span class="task-arrow">→</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { healthCheck, listTasks } from '../api.js'

const serverOk = ref(false)
const version = ref('')
const tasks = ref([])

onMounted(async () => {
  try {
    const h = await healthCheck()
    serverOk.value = h.status === 'ok'
    version.value = h.version
  } catch {
    serverOk.value = false
  }

  try {
    const t = await listTasks({ limit: 5 })
    tasks.value = t
  } catch {
    // 忽略
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
</script>

<style scoped>
.home {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.hero {
  text-align: center;
  padding: 60px 20px;
}

.hero h1 {
  font-size: 2rem;
  color: #1a1a2e;
  margin-bottom: 12px;
}

.subtitle {
  color: #666;
  font-size: 1.1rem;
  margin-bottom: 32px;
}

.actions {
  display: flex;
  justify-content: center;
  gap: 16px;
}

.btn-primary {
  display: inline-block;
  padding: 12px 32px;
  background: #4f46e5;
  color: #fff;
  border-radius: 8px;
  text-decoration: none;
  font-size: 1rem;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #4338ca;
}

.status-bar {
  display: flex;
  gap: 24px;
  padding: 12px 16px;
  background: #f8fafc;
  border-radius: 8px;
  margin-bottom: 30px;
  font-size: 0.9rem;
  color: #64748b;
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.dot.green { background: #22c55e; }
.dot.red { background: #ef4444; }

.recent-tasks h2 {
  font-size: 1.2rem;
  margin-bottom: 12px;
  color: #334155;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.task-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.task-card:hover {
  box-shadow: 0 2px 8px rgba(0,0,0,0.08);
}

.task-type {
  background: #e0e7ff;
  color: #4f46e5;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.85rem;
}

.task-status {
  font-size: 0.85rem;
  padding: 2px 8px;
  border-radius: 4px;
}

.task-status.completed { background: #dcfce7; color: #16a34a; }
.task-status.failed { background: #fef2f2; color: #dc2626; }
.task-status.processing { background: #fef9c3; color: #ca8a04; }
.task-status.pending { background: #f1f5f9; color: #64748b; }

.task-time {
  color: #94a3b8;
  font-size: 0.85rem;
  margin-left: auto;
}

.task-arrow {
  color: #94a3b8;
}
</style>