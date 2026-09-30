<template>
  <div class="records-page">
    <div class="page-header">
      <h1>拉取记录</h1>
      <p>语雀需求拉取的历史记录，可查看详情、重新拉取或删除</p>
    </div>

    <div class="toolbar">
      <el-input v-model="searchQuery" placeholder="搜索需求号、来源名称..." clearable style="max-width: 360px" @input="onSearch" />
    </div>

    <el-table :data="filteredRecords" v-loading="loading" stripe @row-click="r => goDetail(r.id)">
      <el-table-column type="index" :index="1" label="#" width="60" />
      <el-table-column prop="requirement_id" label="需求号" min-width="140">
        <template #default="{ row }">
          <strong>{{ row.requirement_id }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="来源" min-width="200">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.source_name }}</el-tag>
          <span v-if="row.matched_title" class="match-hint" :title="row.matched_title">{{ row.matched_title }}</span>
        </template>
      </el-table-column>
      <el-table-column label="文档数" width="120" align="center">
        <template #default="{ row }">
          {{ row.success }}/{{ row.total }}
          <span v-if="row.failed > 0" class="fail-count">({{ row.failed }}失败)</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="120">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small" effect="dark">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="拉取时间" width="170">
        <template #default="{ row }">
          <span class="time-cell">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="goDetail(row.id)">详情</el-button>
          <el-button size="small" :loading="row._repulling" @click.stop="doRePull(row)">
            {{ row._repulling ? '' : '重新拉取' }}
          </el-button>
          <el-button size="small" type="danger" @click.stop="doDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listYuqueRecords, deleteYuqueRecord, rePullYuqueRecord } from '../api.js'
import { toast } from '../toast.js'

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
    records.value = ((await listYuqueRecords()).records || []).map(r => ({ ...r, _repulling: false }))
  } catch { /* ignore */ }
  finally { loading.value = false }
})

function statusType(s) {
  const map = { success: 'success', partial: 'warning', failed: 'danger' }
  return map[s] || 'info'
}

function statusLabel(s) {
  const map = { success: '成功', partial: '部分成功', failed: '失败' }
  return map[s] || s
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function onSearch() {
  // computed auto-filters
}

function goDetail(id) {
  router.push(`/yuque-records/${id}`)
}

async function doRePull(r) {
  try {
    await ElMessageBox.confirm(`确定重新拉取「${r.requirement_id}」？`, '确认重新拉取', { confirmButtonText: '重新拉取', cancelButtonText: '取消', type: 'warning' })
    r._repulling = true
    await rePullYuqueRecord(r.id)
    records.value = ((await listYuqueRecords()).records || []).map(r => ({ ...r, _repulling: false }))
    toast.success('重新拉取完成！')
  } catch (e) {
    if (e !== 'cancel') toast.error('重新拉取失败: ' + (e.message || '未知错误'))
  } finally {
    r._repulling = false
  }
}

async function doDelete(r) {
  try {
    await ElMessageBox.confirm(`确定删除拉取记录「${r.requirement_id}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteYuqueRecord(r.id)
    records.value = records.value.filter(item => item.id !== r.id)
  } catch (e) {
    toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.records-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { margin-bottom: 16px; }

.match-hint {
  display: inline-block;
  font-size: 0.75rem;
  color: #94a3b8;
  margin-left: 6px;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
}
.fail-count { color: #dc2626; font-size: 0.78rem; }
.time-cell { color: #94a3b8; font-size: 0.85rem; white-space: nowrap; }
</style>