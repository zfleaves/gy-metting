<template>
  <div class="dashboard">
    <div class="page-bar">
      <h2>工作台</h2>
      <router-link to="/upload" class="btn-primary">+ 新建转写</router-link>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总任务数</div>
      </div>
      <div class="stat-card green">
        <div class="stat-value">{{ stats.completed }}</div>
        <div class="stat-label">已完成</div>
      </div>
      <div class="stat-card yellow">
        <div class="stat-value">{{ stats.processing }}</div>
        <div class="stat-label">处理中</div>
      </div>
      <div class="stat-card red">
        <div class="stat-value">{{ stats.failed }}</div>
        <div class="stat-label">失败</div>
      </div>
    </div>

    <!-- 任务列表 -->
    <div class="card">
      <div class="card-header">
        <h3>最近任务</h3>
      </div>
      <div v-if="tasks.length" class="table-wrap">
        <table class="task-table">
          <thead>
            <tr>
              <th>任务 ID</th>
              <th>类型</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id" @click="$router.push(`/task/${task.id}`)">
              <td class="mono">{{ task.id.slice(0, 8) }}...</td>
              <td><span class="tag">{{ task.type }}</span></td>
              <td><span class="status-tag" :class="task.status">{{ statusLabel(task.status) }}</span></td>
              <td class="time">{{ formatTime(task.created_at) }}</td>
              <td><router-link :to="`/task/${task.id}`" class="link">查看 →</router-link></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty">暂无任务，点击右上角「新建转写」开始</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { healthCheck, listTasks } from '../api.js'

const serverOk = ref(false)
const version = ref('')
const tasks = ref([])

const stats = computed(() => {
  const all = tasks.value.length
  return {
    total: all,
    completed: tasks.value.filter(t => t.status === 'completed').length,
    processing: tasks.value.filter(t => t.status === 'processing').length,
    failed: tasks.value.filter(t => t.status === 'failed').length,
  }
})

onMounted(async () => {
  try {
    const h = await healthCheck()
    serverOk.value = h.status === 'ok'
    version.value = h.version
  } catch {
    serverOk.value = false
  }
  try {
    tasks.value = await listTasks({ limit: 20 })
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
  return new Date(t + 'Z').toLocaleString('zh-CN')
}
</script>

<style scoped>
.dashboard {
  padding: 24px;
  max-width: 960px;
}

@media (max-width: 640px) {
  .dashboard {
    padding: 16px;
  }
}

.page-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-bar h2 {
  font-size: 1.3rem;
  color: #1e293b;
  margin: 0;
}

.btn-primary {
  padding: 8px 20px;
  background: #4f46e5;
  color: #fff;
  border-radius: 8px;
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-primary:hover {
  background: #4338ca;
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  border: 1px solid #e2e8f0;
}

.stat-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.stat-label {
  font-size: 0.85rem;
  color: #94a3b8;
}

.stat-card.green .stat-value { color: #16a34a; }
.stat-card.yellow .stat-value { color: #ca8a04; }
.stat-card.red .stat-value { color: #dc2626; }

@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }
}

/* 卡片 */
.card {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  overflow: hidden;
}

.card-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.card-header h3 {
  margin: 0;
  font-size: 1rem;
  color: #334155;
}

.table-wrap {
  overflow-x: auto;
}

.task-table {
  width: 100%;
  border-collapse: collapse;
}

.task-table th {
  text-align: left;
  padding: 10px 20px;
  font-size: 0.8rem;
  color: #94a3b8;
  font-weight: 500;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
}

.task-table td {
  padding: 12px 20px;
  font-size: 0.9rem;
  color: #334155;
  border-bottom: 1px solid #f1f5f9;
}

.task-table tbody tr {
  cursor: pointer;
  transition: background 0.1s;
}

.task-table tbody tr:hover {
  background: #f8fafc;
}

.mono {
  font-family: monospace;
  font-size: 0.85rem;
  color: #64748b;
}

.tag {
  background: #e0e7ff;
  color: #4f46e5;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 0.8rem;
}

.status-tag {
  font-size: 0.8rem;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-tag.completed { background: #dcfce7; color: #16a34a; }
.status-tag.failed { background: #fef2f2; color: #dc2626; }
.status-tag.processing { background: #fef9c3; color: #ca8a04; }
.status-tag.pending { background: #f1f5f9; color: #64748b; }

.time {
  color: #94a3b8;
  font-size: 0.85rem;
}

.link {
  color: #4f46e5;
  text-decoration: none;
  font-size: 0.85rem;
}

.empty {
  padding: 40px;
  text-align: center;
  color: #94a3b8;
  font-size: 0.9rem;
}
</style>