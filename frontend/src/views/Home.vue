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
              <th>任务名称</th>
              <th>类型</th>
              <th>关联会议</th>
              <th>状态</th>
              <th>创建时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="task in tasks" :key="task.id" @click="$router.push(`/task/${task.id}`)">
              <td class="task-name">{{ task.name || task.id.slice(0, 8) + '...' }}</td>
              <td><span class="tag">{{ task.type }}</span></td>
              <td @click.stop>
                <span v-if="task.meeting_id && meetingMap[task.meeting_id]" class="meeting-tag link" @click="openAssoc(task)">
                  📋 {{ meetingMap[task.meeting_id] }}
                </span>
                <span v-else-if="task.meeting_id && !meetingMap[task.meeting_id]" class="meeting-tag missing link" @click="openAssoc(task)">
                  📋 已删除会议
                </span>
                <button v-else class="btn-assoc" @click="openAssoc(task)">关联会议</button>
              </td>
              <td><span class="status-tag" :class="task.status">{{ statusLabel(task.status) }}</span></td>
              <td class="time">{{ formatTime(task.created_at) }}</td>
              <td class="actions">
                <router-link :to="`/task/${task.id}`" class="link" @click.stop>查看</router-link>
                <button class="btn-del" @click.stop="confirmDelete(task)" title="删除">🗑</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="empty">暂无任务，点击右上角「新建转写」开始</div>
    </div>

    <!-- 关联会议弹窗 -->
    <div v-if="assocTask" class="modal-overlay" @click="assocTask = null">
      <div class="modal-box" @click.stop>
        <h3>关联会议</h3>
        <p v-if="assocTask.name">任务：<strong>{{ assocTask.name }}</strong></p>
        <select v-model="assocMeetingId" class="assoc-select">
          <option value="">-- 不关联 --</option>
          <option v-for="m in meetings" :key="m.id" :value="m.id">{{ m.title }}</option>
        </select>
        <div class="modal-actions">
          <button class="btn-cancel" @click="assocTask = null">取消</button>
          <button class="btn-save" @click="doAssoc" :disabled="assocSaving">
            {{ assocSaving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleting" class="modal-overlay" @click="cancelDelete">
      <div class="modal-box" @click.stop>
        <h3>确认删除</h3>
        <p>确定要删除任务「<strong>{{ deleting.name || deleting.id }}</strong>」吗？</p>
        <p class="modal-hint">此操作将同时删除关联的音频文件和转写结果，不可恢复。</p>
        <div class="modal-actions">
          <button class="btn-cancel" @click="cancelDelete">取消</button>
          <button class="btn-danger" @click="doDelete">确认删除</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { healthCheck, listTasks, deleteTask, listMeetings, updateTaskMeeting } from '../api.js'

const serverOk = ref(false)
const version = ref('')
const tasks = ref([])
const meetings = ref([])
const meetingMap = ref({})
const deleting = ref(null)
const assocTask = ref(null)
const assocMeetingId = ref('')
const assocSaving = ref(false)

const stats = computed(() => {
  const all = tasks.value.length
  return {
    total: all,
    completed: tasks.value.filter(t => t.status === 'completed').length,
    processing: tasks.value.filter(t => t.status === 'processing').length,
    failed: tasks.value.filter(t => t.status === 'failed').length,
  }
})

onMounted(() => { loadTasks() })

async function loadTasks() {
  try {
    const h = await healthCheck()
    serverOk.value = h.status === 'ok'
    version.value = h.version
  } catch { serverOk.value = false }
  try {
    tasks.value = await listTasks({ limit: 20 })
    // 加载会议列表
    meetings.value = await listMeetings()
    const map = {}
    for (const m of meetings.value) {
      map[m.id] = m.title
    }
    meetingMap.value = map
  } catch { /* ignore */ }
}

function openAssoc(task) {
  assocTask.value = task
  assocMeetingId.value = task.meeting_id || ''
}

async function doAssoc() {
  if (!assocTask.value) return
  assocSaving.value = true
  try {
    await updateTaskMeeting(assocTask.value.id, assocMeetingId.value || null)
    assocTask.value.meeting_id = assocMeetingId.value || null
    assocTask.value = null
  } catch (e) {
    alert('保存失败: ' + (e.message || '未知错误'))
  } finally {
    assocSaving.value = false
  }
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
  deleting.value = task
}

async function doDelete() {
  if (!deleting.value) return
  const task = deleting.value
  try {
    await deleteTask(task.id)
    tasks.value = tasks.value.filter(t => t.id !== task.id)
  } catch (e) {
    alert('删除失败: ' + (e.message || '未知错误'))
  } finally {
    deleting.value = null
  }
}

function cancelDelete() {
  deleting.value = null
}
</script>

<style scoped>
.dashboard { padding: 24px; }
@media (max-width: 640px) { .dashboard { padding: 16px; } }

.page-bar { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.page-bar h2 { font-size: 1.3rem; color: #1e293b; margin: 0; }
.btn-primary { padding: 8px 20px; background: #4f46e5; color: #fff; border-radius: 8px; text-decoration: none; font-size: 0.9rem; font-weight: 500; transition: background 0.2s; }
.btn-primary:hover { background: #4338ca; }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: #fff; border-radius: 10px; padding: 20px; border: 1px solid #e2e8f0; }
.stat-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; margin-bottom: 4px; }
.stat-label { font-size: 0.85rem; color: #94a3b8; }
.stat-card.green .stat-value { color: #16a34a; }
.stat-card.yellow .stat-value { color: #ca8a04; }
.stat-card.red .stat-value { color: #dc2626; }
@media (max-width: 640px) { .stats-row { grid-template-columns: repeat(2, 1fr); } }

.card { background: #fff; border-radius: 10px; border: 1px solid #e2e8f0; overflow: hidden; }
.card-header { padding: 16px 20px; border-bottom: 1px solid #f1f5f9; }
.card-header h3 { margin: 0; font-size: 1rem; color: #334155; }
.table-wrap { overflow-x: auto; }
.task-table { width: 100%; border-collapse: collapse; }
.task-table th { text-align: left; padding: 10px 20px; font-size: 0.8rem; color: #94a3b8; font-weight: 500; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.task-table td { padding: 12px 20px; font-size: 0.9rem; color: #334155; border-bottom: 1px solid #f1f5f9; }
.task-table tbody tr { cursor: pointer; transition: background 0.1s; }
.task-table tbody tr:hover { background: #f8fafc; }
.task-name { font-size: 0.9rem; color: #1e293b; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag { background: #e0e7ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
.status-tag { font-size: 0.8rem; padding: 2px 8px; border-radius: 4px; }
.status-tag.completed { background: #dcfce7; color: #16a34a; }
.status-tag.failed { background: #fef2f2; color: #dc2626; }
.status-tag.processing { background: #fef9c3; color: #ca8a04; }
.status-tag.pending { background: #f1f5f9; color: #64748b; }
.time { color: #94a3b8; font-size: 0.85rem; }
.link { color: #4f46e5; text-decoration: none; font-size: 0.85rem; margin-right: 8px; }
.actions { white-space: nowrap; }
.btn-del { background: none; border: 1px solid #e2e8f0; border-radius: 4px; padding: 2px 6px; cursor: pointer; font-size: 0.85rem; opacity: 0.5; transition: opacity 0.15s; }
.btn-del:hover { opacity: 1; border-color: #dc2626; }

/* 关联会议 */
.meeting-tag { color: #4f46e5; font-size: 0.83rem; }
.meeting-tag.link { cursor: pointer; }
.meeting-tag.link:hover { text-decoration: underline; }
.meeting-tag.missing { color: #94a3b8; }
.btn-assoc { padding: 3px 10px; border: 1px dashed #cbd5e1; background: none; border-radius: 4px; cursor: pointer; font-size: 0.78rem; color: #94a3b8; }
.btn-assoc:hover { border-color: #4f46e5; color: #4f46e5; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; border-radius: 12px; padding: 24px; max-width: 420px; width: 90%; box-shadow: 0 8px 30px rgba(0,0,0,0.15); }
.modal-box h3 { margin: 0 0 12px; font-size: 1.1rem; color: #1e293b; }
.modal-box p { margin: 0 0 12px; color: #64748b; font-size: 0.9rem; }
.modal-hint { color: #94a3b8 !important; font-size: 0.8rem !important; }
.assoc-select { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; margin-bottom: 4px; box-sizing: border-box; }
.assoc-select:focus { border-color: #4f46e5; }
.modal-actions { display: flex; gap: 12px; justify-content: flex-end; margin-top: 16px; }
.btn-cancel, .btn-danger, .btn-save { padding: 8px 20px; border-radius: 6px; font-size: 0.9rem; border: none; cursor: pointer; }
.btn-cancel { background: #f1f5f9; color: #334155; }
.btn-danger { background: #dc2626; color: #fff; }
.btn-save { background: #4f46e5; color: #fff; }
.btn-save:disabled { opacity: 0.6; }

.empty { padding: 40px; text-align: center; color: #94a3b8; font-size: 0.9rem; }
</style>