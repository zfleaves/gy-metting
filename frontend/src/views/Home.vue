<template>
  <div class="dashboard">
    <div class="page-bar">
      <h2>工作台</h2>
      <el-button type="primary" @click="$router.push('/upload')">+ 新建转写</el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ stats.tasks.total }}</div>
        <div class="stat-label">总任务数</div>
      </el-card>
      <el-card shadow="never" class="stat-card green">
        <div class="stat-value">{{ stats.tasks.completed }}</div>
        <div class="stat-label">已完成</div>
      </el-card>
      <el-card shadow="never" class="stat-card yellow">
        <div class="stat-value">{{ stats.tasks.processing }}</div>
        <div class="stat-label">处理中</div>
      </el-card>
      <el-card shadow="never" class="stat-card red">
        <div class="stat-value">{{ stats.tasks.failed }}</div>
        <div class="stat-label">失败</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ stats.minutes.total }}</div>
        <div class="stat-label">AI 纪要</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ stats.meetings.total }}</div>
        <div class="stat-label">会议</div>
      </el-card>
    </div>

    <!-- 任务列表 -->
    <el-card shadow="never" class="card">
      <template #header>
        <span>最近任务</span>
      </template>

      <el-table :data="tasks" v-loading="loading" stripe size="small" style="width: 100%" @row-click="row => $router.push(`/task/${row.id}`)">
        <el-table-column prop="name" label="任务名称" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.name || row.id.slice(0, 8) + '...' }}
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="70">
          <template #default="{ row }">
            <el-tag size="small">{{ row.type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="关联会议" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.meeting_id && meetingMap[row.meeting_id]" class="meeting-link" @click.stop="router.push(`/meeting/${row.meeting_id}`)">
              📋 {{ meetingMap[row.meeting_id] }}
            </span>
            <span v-else-if="row.meeting_id" class="meeting-link missing">📋 已删除</span>
            <el-button v-else size="small" @click.stop="openAssoc(row)">关联</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="75">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small" effect="dark">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="155">
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click.stop="$router.push(`/task/${row.id}`)">查看</el-button>
            <el-button size="small" type="danger" @click.stop="confirmDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!tasks.length && !loading" class="empty-hint">
        暂无任务，点击右上角「新建转写」开始
      </div>
    </el-card>

    <!-- 关联会议弹窗 -->
    <el-dialog v-model="assocVisible" title="关联会议" width="420">
      <p v-if="assocTask?.name">任务：<strong>{{ assocTask.name }}</strong></p>
      <el-select v-model="assocMeetingId" placeholder="选择会议" class="w-full" clearable filterable>
        <el-option label="-- 不关联 --" value="" />
        <el-option v-for="m in meetings" :key="m.id" :label="m.title" :value="m.id" />
      </el-select>
      <template #footer>
        <el-button @click="assocVisible = false">取消</el-button>
        <el-button type="primary" @click="doAssoc" :loading="assocSaving">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { healthCheck, listTasks, deleteTask, listMeetings, updateTaskMeeting, getStats } from '../api.js'
import { toast } from '../toast.js'

const router = useRouter()

const serverOk = ref(false)
const version = ref('')
const tasks = ref([])
const meetings = ref([])
const meetingMap = ref({})
const loading = ref(true)
const deleting = ref(null)
const assocVisible = ref(false)
const assocTask = ref(null)
const assocMeetingId = ref('')
const assocSaving = ref(false)
const stats = ref({ tasks: { total: 0, completed: 0, processing: 0, pending: 0, failed: 0 }, minutes: { total: 0 }, meetings: { total: 0 } })

onMounted(() => { loadTasks() })

async function loadTasks() {
  loading.value = true
  try {
    const h = await healthCheck()
    serverOk.value = h.status === 'ok'
    version.value = h.version
  } catch { serverOk.value = false }
  try {
    const res = await listTasks({ limit: 20 })
    tasks.value = res.records || res
    meetings.value = (await listMeetings({ limit: 200 })).records || []
    const map = {}
    for (const m of meetings.value) {
      map[m.id] = m.title
    }
    meetingMap.value = map
  } catch { /* ignore */ }
  try {
    stats.value = await getStats()
  } catch { /* ignore */ }
  finally { loading.value = false }
}

function openAssoc(task) {
  assocTask.value = task
  assocMeetingId.value = task.meeting_id || ''
  assocVisible.value = true
}

async function doAssoc() {
  if (!assocTask.value) return
  assocSaving.value = true
  try {
    await updateTaskMeeting(assocTask.value.id, assocMeetingId.value || null)
    assocTask.value.meeting_id = assocMeetingId.value || null
    assocVisible.value = false
    assocTask.value = null
  } catch (e) {
    toast.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    assocSaving.value = false
  }
}

function statusType(s) {
  const map = { completed: 'success', failed: 'danger', processing: 'warning', pending: 'info' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { pending: '等待中', processing: '处理中', completed: '已完成', failed: '失败' }
  return map[s] || s
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function confirmDelete(task) {
  ElMessageBox.confirm(
    `确定要删除任务「${task.name || task.id}」吗？`,
    '确认删除',
    { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning', message: '此操作将同时删除关联的音频文件和转写结果，不可恢复。' }
  ).then(async () => {
    try {
      await deleteTask(task.id)
      tasks.value = tasks.value.filter(t => t.id !== task.id)
      toast.success('已删除')
    } catch (e) {
      toast.error('删除失败: ' + (e.message || '未知错误'))
    }
  }).catch(() => {})
}
</script>

<style scoped>
.dashboard { padding: 24px; }
@media (max-width: 640px) { .dashboard { padding: 16px; } }

.page-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-bar h2 { font-size: 1.3rem; color: #1e293b; margin: 0; }

.stats-row { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 24px; }
@media (max-width: 640px) { .stats-row { grid-template-columns: repeat(3, 1fr); gap: 8px; } }

.stat-card { text-align: center; }
.stat-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
.stat-label { font-size: 0.85rem; color: #94a3b8; }
.stat-card.green .stat-value { color: #16a34a; }
.stat-card.yellow .stat-value { color: #ca8a04; }
.stat-card.red .stat-value { color: #dc2626; }

.card { margin-bottom: 24px; }

.meeting-link { color: #4f46e5; font-size: 0.83rem; cursor: pointer; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; display: block; }
.meeting-link:hover { text-decoration: underline; }
.meeting-link.missing { color: #94a3b8; cursor: default; }

.time-text { color: #94a3b8; font-size: 0.85rem; white-space: nowrap; }
.empty-hint { padding: 40px; text-align: center; color: #94a3b8; font-size: 0.9rem; }
.w-full { width: 100%; }
</style>