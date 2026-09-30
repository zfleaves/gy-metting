<template>
  <div class="minutes-page">
    <div class="page-header">
      <h1>AI 纪要</h1>
      <p>查看和管理 AI 生成的会议纪要记录</p>
    </div>

    <div class="toolbar">
      <el-input v-model="searchQuery" class="search-input" placeholder="搜索标题..." clearable @input="onSearch" />
      <el-select v-model="filterType" class="filter-select" placeholder="全部类型" clearable @change="onSearch">
        <el-option label="全部类型" value="" />
        <el-option label="通用" value="通用" />
        <el-option label="需求评审" value="需求评审" />
        <el-option label="技术评审" value="技术评审" />
        <el-option label="周会" value="周会" />
      </el-select>
      <el-date-picker v-model="dateFrom" type="date" placeholder="起始日期" class="filter-date" value-format="YYYY-MM-DD" @change="onSearch" />
      <el-date-picker v-model="dateTo" type="date" placeholder="结束日期" class="filter-date" value-format="YYYY-MM-DD" @change="onSearch" />
      <div class="toolbar-right">
        <span class="total-hint">共 {{ total }} 条</span>
        <el-button type="primary" @click="$router.push('/minutes/new')">+ 新建纪要</el-button>
      </div>
    </div>

    <el-table :data="records" v-loading="loading" stripe style="width: 100%" @row-click="goDetail">
      <el-table-column type="index" :index="offset + 1" label="#" width="60" />
      <el-table-column prop="title" label="标题" min-width="180">
        <template #default="{ row }">
          <strong>{{ row.title || '未命名' }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="meeting_type" label="类型" width="100">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.meeting_type }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="task_name" label="关联任务" min-width="140" show-overflow-tooltip />
      <el-table-column prop="meeting_title" label="关联会议" min-width="140" show-overflow-tooltip />
      <el-table-column prop="token_count" label="Token" width="80" align="center" />
      <el-table-column label="生成时间" width="170">
        <template #default="{ row }">
          <span class="time-cell">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="$router.push(`/minutes/${row.id}`)">详情</el-button>
          <el-button size="small" @click.stop="doExport(row)">导出</el-button>
          <el-button size="small" type="danger" @click.stop="doDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div v-if="total > limit" class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="limit"
        :total="total"
        layout="prev, pager, next, total"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listMinutes, deleteMinutes, exportMinutes } from '../api.js'
import { toast } from '../toast.js'

const router = useRouter()

const records = ref([])
const total = ref(0)
const loading = ref(true)
const searchQuery = ref('')
const filterType = ref('')
const dateFrom = ref('')
const dateTo = ref('')
const offset = ref(0)
const limit = 20
let searchTimer = null

const currentPage = computed({
  get: () => Math.floor(offset.value / limit) + 1,
  set: (val) => { offset.value = (val - 1) * limit },
})

onMounted(() => load())

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { offset.value = 0; load() }, 300)
}

function onPageChange(page) {
  offset.value = (page - 1) * limit
  load()
}

function goDetail(row) {
  router.push(`/minutes/${row.id}`)
}

async function load() {
  loading.value = true
  try {
    const res = await listMinutes({
      search: searchQuery.value,
      meeting_type: filterType.value || undefined,
      date_from: dateFrom.value || undefined,
      date_to: dateTo.value || undefined,
      limit,
      offset: offset.value,
    })
    records.value = res.records
    total.value = res.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

async function doExport(r) {
  try {
    const resp = await exportMinutes(r.id)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${r.title || '会议纪要'}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('导出成功')
  } catch (e) {
    toast.error('导出失败: ' + (e.message || '未知错误'))
  }
}

async function doDelete(r) {
  try {
    await ElMessageBox.confirm(`确定删除纪要「${r.title}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteMinutes(r.id)
    records.value = records.value.filter(item => item.id !== r.id)
    total.value--
    toast.success('已删除')
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.minutes-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; gap: 8px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
.search-input { width: 200px; }
.filter-select { width: 140px; }
.filter-date { width: 150px; }
.toolbar-right { display: flex; align-items: center; gap: 12px; margin-left: auto; }
.total-hint { font-size: 0.85rem; color: #94a3b8; }

.time-cell { color: #94a3b8; font-size: 0.85rem; white-space: nowrap; }

.pagination-wrap { display: flex; justify-content: center; margin-top: 16px; }
</style>