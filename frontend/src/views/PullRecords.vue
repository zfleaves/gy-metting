<template>
  <div class="records-page">
    <div class="page-header">
      <h1>拉取记录</h1>
      <p>语雀需求拉取的历史记录，可查看详情、重新拉取或删除</p>
    </div>

    <!-- 搜索栏 -->
    <div class="toolbar">
      <input
        v-model="searchQuery"
        class="search-input"
        placeholder="搜索需求号、来源名称..."
      />
    </div>

    <div class="table-wrap">
      <table class="yuque-table">
        <thead>
          <tr>
            <th>#</th>
            <th>需求号</th>
            <th>来源</th>
            <th>文档数</th>
            <th>状态</th>
            <th>拉取时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="7" class="empty-cell">加载中...</td>
          </tr>
          <tr v-else-if="!filteredRecords.length">
            <td colspan="7" class="empty-cell">{{ records.length ? '无匹配记录' : '暂无拉取记录' }}</td>
          </tr>
          <tr v-for="(r, idx) in filteredRecords" :key="r.id">
            <td class="cell-idx">{{ idx + 1 }}</td>
            <td><strong>{{ r.requirement_id }}</strong></td>
            <td>
              <span class="source-tag">{{ r.source_name }}</span>
              <span v-if="r.matched_title" class="match-hint" :title="r.matched_title">{{ r.matched_title }}</span>
            </td>
            <td class="cell-center">
              {{ r.success }}/{{ r.total }}
              <span v-if="r.failed > 0" class="fail-count">({{ r.failed }}失败)</span>
            </td>
            <td>
              <span class="status-badge" :class="'status-' + r.status">
                {{ statusLabel(r.status) }}
              </span>
            </td>
            <td class="time-cell">{{ formatTime(r.created_at) }}</td>
            <td>
              <div class="action-btns">
                <button class="btn-detail" @click="goDetail(r.id)">详情</button>
                <button class="btn-repull" :disabled="r._repulling" @click="doRePull(r)">
                  {{ r._repulling ? '拉取中...' : '重新拉取' }}
                </button>
                <button class="btn-del" @click="doDelete(r)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listYuqueRecords, deleteYuqueRecord, rePullYuqueRecord } from '../api.js'

const router = useRouter()
const records = ref([])
const loading = ref(true)
const searchQuery = ref('')

const filteredRecords = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return records.value
  return records.value.filter(r =>
    r.requirement_id.toLowerCase().includes(q) ||
    r.source_name.toLowerCase().includes(q) ||
    (r.matched_title || '').toLowerCase().includes(q)
  )
})

onMounted(async () => {
  try {
    records.value = (await listYuqueRecords()).map(r => ({ ...r, _repulling: false }))
  } catch { /* ignore */ }
  finally { loading.value = false }
})

function statusLabel(s) {
  const map = { success: '成功', partial: '部分成功', failed: '失败' }
  return map[s] || s
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function goDetail(id) {
  router.push(`/yuque-records/${id}`)
}

async function doRePull(r) {
  if (!confirm(`确定重新拉取「${r.requirement_id}」？`)) return
  r._repulling = true
  try {
    await rePullYuqueRecord(r.id)
    records.value = (await listYuqueRecords()).map(r => ({ ...r, _repulling: false }))
    alert('重新拉取完成！')
  } catch (e) {
    alert('重新拉取失败: ' + (e.message || '未知错误'))
  } finally {
    r._repulling = false
  }
}

async function doDelete(r) {
  if (!confirm(`确定删除拉取记录「${r.requirement_id}」？`)) return
  try {
    await deleteYuqueRecord(r.id)
    records.value = records.value.filter(item => item.id !== r.id)
  } catch (e) {
    alert('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.records-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

/* 搜索栏 */
.toolbar { margin-bottom: 16px; }
.search-input {
  width: 100%;
  max-width: 360px;
  padding: 8px 14px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
  box-sizing: border-box;
}
.search-input:focus { border-color: #4f46e5; }

.table-wrap {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  overflow: hidden;
}
.yuque-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
  table-layout: auto;
}
.yuque-table thead { background: #f8fafc; }
.yuque-table th {
  text-align: left;
  padding: 10px 14px;
  font-weight: 600;
  color: #64748b;
  font-size: 0.82rem;
  border-bottom: 1px solid #e2e8f0;
  white-space: nowrap;
}
.yuque-table td {
  padding: 12px 14px;
  border-bottom: 1px solid #f1f5f9;
  color: #334155;
}
.yuque-table tbody tr:hover { background: #f8fafc; }
.yuque-table tbody tr:last-child td { border-bottom: none; }
.empty-cell { text-align: center; color: #94a3b8; padding: 40px 14px !important; }
.cell-idx { color: #94a3b8; width: 1%; white-space: nowrap; }
.cell-center { text-align: center; }
.time-cell { color: #94a3b8; white-space: nowrap; }

.source-tag {
  font-size: 0.75rem;
  background: #eef2ff;
  color: #4f46e5;
  padding: 2px 8px;
  border-radius: 4px;
  white-space: nowrap;
}
.match-hint {
  display: inline-block;
  font-size: 0.75rem;
  color: #94a3b8;
  margin-left: 6px;
  max-width: 260px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.fail-count { color: #dc2626; font-size: 0.78rem; }

.status-badge { font-size: 0.75rem; padding: 2px 10px; border-radius: 10px; font-weight: 500; white-space: nowrap; }
.status-success { background: #f0fdf4; color: #16a34a; }
.status-partial { background: #fffbeb; color: #d97706; }
.status-failed { background: #fef2f2; color: #dc2626; }

.action-btns { display: flex; gap: 6px; width: 1%; white-space: nowrap; }
.btn-detail { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #4f46e5; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-detail:hover { background: #eef2ff; }
.btn-repull { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #059669; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-repull:hover { background: #f0fdf4; }
.btn-repull:disabled { opacity: 0.6; cursor: not-allowed; }
.btn-del { padding: 4px 12px; border: 1px solid #fecaca; background: #fff; color: #dc2626; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-del:hover { background: #fef2f2; }
</style>