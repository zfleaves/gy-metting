<template>
  <div class="minutes-page">
    <div class="page-header">
      <h1>AI 纪要</h1>
      <p>查看和管理 AI 生成的会议纪要记录</p>
    </div>

    <div class="toolbar">
      <input v-model="searchQuery" class="search-input" placeholder="搜索标题..." @input="onSearch" />
      <div class="toolbar-right">
        <span class="total-hint">共 {{ total }} 条</span>
        <router-link to="/minutes/new" class="btn-add">+ 新建纪要</router-link>
      </div>
    </div>

    <div class="table-wrap">
      <table class="minutes-table">
        <thead>
          <tr>
            <th>#</th>
            <th>标题</th>
            <th>类型</th>
            <th>关联任务</th>
            <th>关联会议</th>
            <th>Token</th>
            <th>生成时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="8" class="empty-cell">加载中...</td></tr>
          <tr v-else-if="!records.length"><td colspan="8" class="empty-cell">暂无纪要记录</td></tr>
          <tr v-for="(r, idx) in records" :key="r.id">
            <td class="cell-idx">{{ offset + idx + 1 }}</td>
            <td><strong>{{ r.title || '未命名' }}</strong></td>
            <td><span class="type-tag">{{ r.meeting_type }}</span></td>
            <td class="cell-name" :title="r.task_name">{{ r.task_name || '-' }}</td>
            <td class="cell-name" :title="r.meeting_title">{{ r.meeting_title || '-' }}</td>
            <td class="cell-center">{{ r.token_count }}</td>
            <td class="time-cell">{{ formatTime(r.created_at) }}</td>
            <td>
              <div class="action-btns">
                <router-link :to="`/minutes/${r.id}`" class="btn-detail">详情</router-link>
                <button class="btn-export" @click="doExport(r)">导出 MD</button>
                <button class="btn-del" @click="doDelete(r)">删除</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 分页 -->
    <div v-if="total > limit" class="pagination">
      <button :disabled="offset === 0" @click="goPage(offset - limit)">← 上一页</button>
      <span>{{ currentPage }} / {{ totalPages }}</span>
      <button :disabled="offset + limit >= total" @click="goPage(offset + limit)">下一页 →</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { listMinutes, deleteMinutes, exportMinutes } from '../api.js'
import { toast } from '../toast.js'

const records = ref([])
const total = ref(0)
const loading = ref(true)
const searchQuery = ref('')
const offset = ref(0)
const limit = 20
let searchTimer = null

const currentPage = computed(() => Math.floor(offset.value / limit) + 1)
const totalPages = computed(() => Math.ceil(total.value / limit))

onMounted(() => load())

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { offset.value = 0; load() }, 300)
}

async function load() {
  loading.value = true
  try {
    const res = await listMinutes({ search: searchQuery.value, limit, offset: offset.value })
    records.value = res.records
    total.value = res.total
  } catch { /* ignore */ }
  finally { loading.value = false }
}

function goPage(newOffset) {
  offset.value = Math.max(0, newOffset)
  load()
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
  if (!confirm(`确定删除纪要「${r.title}」？`)) return
  try {
    await deleteMinutes(r.id)
    records.value = records.value.filter(item => item.id !== r.id)
    total.value--
    toast.success('已删除')
  } catch (e) {
    toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.minutes-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; justify-content: space-between; }
.search-input { padding: 8px 14px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.9rem; outline: none; width: 320px; }
.search-input:focus { border-color: #4f46e5; }
.toolbar-right { display: flex; align-items: center; gap: 12px; }
.total-hint { font-size: 0.85rem; color: #94a3b8; }
.btn-add { padding: 8px 18px; background: #4f46e5; color: #fff; border-radius: 6px; text-decoration: none; font-size: 0.9rem; }
.btn-add:hover { background: #4338ca; }

.table-wrap { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
.minutes-table { width: 100%; border-collapse: collapse; font-size: 0.88rem; }
.minutes-table thead { background: #f8fafc; }
.minutes-table th { text-align: left; padding: 10px 14px; font-weight: 600; color: #64748b; font-size: 0.82rem; border-bottom: 1px solid #e2e8f0; white-space: nowrap; }
.minutes-table td { padding: 12px 14px; border-bottom: 1px solid #f1f5f9; color: #334155; }
.minutes-table tbody tr:hover { background: #f8fafc; }
.minutes-table tbody tr:last-child td { border-bottom: none; }
.empty-cell { text-align: center; color: #94a3b8; padding: 40px 14px !important; }
.cell-idx { color: #94a3b8; width: 1%; white-space: nowrap; }
.cell-center { text-align: center; }
.time-cell { color: #94a3b8; white-space: nowrap; }
.cell-name { max-width: 180px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #64748b; font-size: 0.85rem; }
.type-tag { font-size: 0.75rem; background: #eef2ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; }

.action-btns { display: flex; gap: 6px; }
.btn-detail { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #4f46e5; border-radius: 4px; cursor: pointer; font-size: 0.8rem; text-decoration: none; display: inline-block; }
.btn-detail:hover { background: #eef2ff; }
.btn-export { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; color: #059669; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-export:hover { background: #f0fdf4; }
.btn-del { padding: 4px 12px; border: 1px solid #fecaca; background: #fff; color: #dc2626; border-radius: 4px; cursor: pointer; font-size: 0.8rem; }
.btn-del:hover { background: #fef2f2; }

/* 分页 */
.pagination { display: flex; align-items: center; justify-content: center; gap: 16px; margin-top: 16px; }
.pagination button { padding: 6px 16px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #64748b; }
.pagination button:disabled { opacity: 0.4; cursor: not-allowed; }
.pagination button:hover:not(:disabled) { border-color: #4f46e5; color: #4f46e5; }
.pagination span { font-size: 0.85rem; color: #94a3b8; }
</style>