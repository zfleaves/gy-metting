<template>
  <div class="meetings-page">
    <div class="page-header">
      <h1>参考文档</h1>
      <p>创建会议/需求记录，关联业务背景和参考文档，供音频转写时选择</p>
    </div>

    <div class="toolbar">
      <el-input v-model="searchQuery" class="search-input" placeholder="搜索会议标题..." clearable @input="() => {}" />
      <el-button type="primary" @click="openCreateModal">+ 新建会议</el-button>
    </div>

    <el-table :data="filteredMeetings" v-loading="loading" stripe @row-click="m => goDetail(m.id)">
      <el-table-column type="index" :index="1" label="#" width="60" />
      <el-table-column prop="title" label="会议标题" min-width="180">
        <template #default="{ row }">
          <strong>{{ row.title }}</strong>
        </template>
      </el-table-column>
      <el-table-column prop="background" label="业务背景" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.background || '-' }}
        </template>
      </el-table-column>
      <el-table-column label="关联文档" width="120" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.snapshot_ids?.length || 0 }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">
          <span class="time-cell">{{ formatTime(row.created_at) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click.stop="goDetail(row.id)">详情</el-button>
          <el-button size="small" @click.stop="openEditModal(row)">编辑</el-button>
          <el-button size="small" type="danger" @click.stop="doDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <CreateMeetingModal
      :visible="showModal"
      :editing-id="editingId"
      :edit-data="editingId ? form : null"
      @close="closeModal"
      @saved="onMeetingSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  listMeetings, deleteMeeting, listYuqueRecords,
} from '../api.js'
import CreateMeetingModal from '../components/CreateMeetingModal.vue'
import { toast } from '../toast.js'

const router = useRouter()

const meetings = ref([])
const loading = ref(true)
const searchQuery = ref('')

const showModal = ref(false)
const editingId = ref(null)
const form = ref({ title: '', background: '', snapshot_ids: [] })

const filteredMeetings = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return meetings.value
  return meetings.value.filter(m => m.title.toLowerCase().includes(q))
})

onMounted(async () => {
  try { meetings.value = (await listMeetings()).records || [] } catch { /* ignore */ }
  finally { loading.value = false }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function goDetail(id) {
  router.push(`/meeting/${id}`)
}

function openCreateModal() {
  editingId.value = null
  showModal.value = true
}

function openEditModal(m) {
  editingId.value = m.id
  form.value = {
    title: m.title,
    background: m.background || '',
    snapshot_ids: m.snapshot_ids || [],
  }
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingId.value = null
}

async function onMeetingSaved() {
  meetings.value = (await listMeetings()).records || []
  closeModal()
}

async function doDelete(m) {
  try {
    await ElMessageBox.confirm(`确定删除会议「${m.title}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteMeeting(m.id)
    meetings.value = meetings.value.filter(item => item.id !== m.id)
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.meetings-page { padding: 24px; }
.page-header { margin-bottom: 16px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.9rem; margin: 0; }

.toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.search-input { max-width: 320px; }

.time-cell { color: #94a3b8; font-size: 0.85rem; white-space: nowrap; }
</style>