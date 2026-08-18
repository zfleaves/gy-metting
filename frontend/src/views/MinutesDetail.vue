<template>
  <div class="detail-page">
    <div class="detail-topbar">
      <router-link to="/minutes" class="btn-back">← 返回列表</router-link>
      <div class="topbar-info" v-if="record">
        <strong>{{ record.title }}</strong>
        <span class="type-tag">{{ record.meeting_type }}</span>
      </div>
      <div class="topbar-actions" v-if="record">
        <button class="btn-export" @click="doExport">📥 导出 MD</button>
        <router-link :to="`/minutes/new?task_id=${record.task_id}`" v-if="record.task_id" class="btn-regen">📝 重新生成</router-link>
        <button class="btn-del" @click="doDelete">🗑 删除</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!record" class="loading">纪要不存在</div>

    <template v-else>
      <!-- 元信息 -->
      <div class="meta-section">
        <div class="meta-item">
          <span class="meta-label">会议类型</span>
          <span class="meta-value">{{ record.meeting_type }}</span>
        </div>
        <div class="meta-item" v-if="record.task_name">
          <span class="meta-label">关联任务</span>
          <span class="meta-value">
            <a :href="`/task/${record.task_id}`" target="_blank" class="link">{{ record.task_name }}</a>
          </span>
        </div>
        <div class="meta-item" v-if="record.meeting_title">
          <span class="meta-label">关联会议</span>
          <span class="meta-value">
            <a :href="`/meeting/${record.meeting_id}`" target="_blank" class="link">{{ record.meeting_title }}</a>
          </span>
        </div>
        <div class="meta-item" v-if="meetingDocs.length">
          <span class="meta-label">参考文档</span>
          <span class="meta-value">
            <span v-for="doc in meetingDocs" :key="doc.id" class="doc-tag">
              <a :href="`/meeting/${record.meeting_id}`" target="_blank" class="link">{{ doc.title }}</a>
            </span>
          </span>
        </div>
        <div class="meta-item">
          <span class="meta-label">Token 数</span>
          <span class="meta-value">{{ record.token_count }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">生成时间</span>
          <span class="meta-value">{{ formatTime(record.created_at) }}</span>
        </div>
      </div>

      <!-- 内容 -->
      <div class="content-section">
        <div class="content-body yuque-doc" v-html="renderedContent"></div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getMinutes, deleteMinutes, exportMinutes, getMeeting } from '../api.js'
import { marked } from 'marked'
import { toast } from '../toast.js'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const router = useRouter()
const record = ref(null)
const loading = ref(true)
const meetingDocs = ref([])

const renderedContent = computed(() => {
  if (!record.value?.content) return ''
  try {
    let html = marked.parse(record.value.content)
    html = html.replace(/<img src="https:\/\/cdn\.nlark\.com([^"]+)"/g, (m, p) => {
      return `<img src="/api/yuque-image-proxy?url=${encodeURIComponent('https://cdn.nlark.com' + p)}"`
    })
    // 变更记录高亮：给包含 ⚠️ 的单元格加上高亮类
    html = html.replace(
      /<td>(⚠️[^<]*)<\/td>/g,
      '<td class="change-highlight">$1</td>'
    )
    return html
  } catch { return record.value.content }
})

onMounted(async () => {
  try {
    record.value = await getMinutes(route.params.id)
    // 加载关联会议的文档
    if (record.value?.meeting_id) {
      try {
        const meeting = await getMeeting(record.value.meeting_id)
        if (meeting?.snapshots?.length) {
          meetingDocs.value = meeting.snapshots
        }
      } catch { /* ignore */ }
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

async function doExport() {
  if (!record.value) return
  try {
    const resp = await exportMinutes(route.params.id)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${record.value.title || '会议纪要'}.md`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('导出成功')
  } catch (e) {
    toast.error('导出失败: ' + (e.message || '未知错误'))
  }
}

async function doDelete() {
  if (!confirm(`确定删除纪要「${record.value.title}」？`)) return
  try {
    await deleteMinutes(route.params.id)
    toast.success('已删除')
    router.push('/minutes')
  } catch (e) {
    toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.detail-page { padding: 0; }
.detail-topbar { display: flex; align-items: center; gap: 12px; padding: 14px 24px; background: #fff; border-bottom: 1px solid #e2e8f0; position: sticky; top: 0; z-index: 10; }
.btn-back { padding: 6px 14px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.82rem; color: #64748b; text-decoration: none; }
.btn-back:hover { border-color: #4f46e5; color: #4f46e5; }
.topbar-info { flex: 1; display: flex; align-items: center; gap: 8px; }
.topbar-info strong { font-size: 0.95rem; color: #1e293b; }
.topbar-actions { display: flex; gap: 6px; }
.btn-export { padding: 6px 14px; border: 1px solid #059669; background: #fff; color: #059669; border-radius: 6px; cursor: pointer; font-size: 0.8rem; text-decoration: none; }
.btn-export:hover { background: #f0fdf4; }
.btn-regen { padding: 6px 14px; border: 1px solid #d97706; background: #fff; color: #d97706; border-radius: 6px; cursor: pointer; font-size: 0.8rem; text-decoration: none; }
.btn-regen:hover { background: #fffbeb; }
.btn-del { padding: 6px 14px; border: 1px solid #fecaca; background: #fff; color: #dc2626; border-radius: 6px; cursor: pointer; font-size: 0.8rem; }
.btn-del:hover { background: #fef2f2; }

.loading { text-align: center; padding: 60px 0; color: #94a3b8; }

.meta-section { display: flex; flex-wrap: wrap; gap: 4px 24px; padding: 16px 24px; background: #f8fafc; border-bottom: 1px solid #e2e8f0; }
.meta-item { display: flex; align-items: center; gap: 6px; }
.meta-label { font-size: 0.78rem; color: #94a3b8; }
.meta-value { font-size: 0.85rem; color: #1e293b; }
.link { color: #4f46e5; text-decoration: underline; }
.type-tag { font-size: 0.75rem; background: #eef2ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; }
.doc-tag { margin-right: 8px; }
.doc-tag .link { font-size: 0.82rem; }

.content-section { padding: 24px 32px; }
.content-body { max-width: 900px; margin: 0 auto; }

.yuque-doc { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', Arial, sans-serif; font-size: 15px; line-height: 1.8; color: #262626; word-wrap: break-word; }
.yuque-doc :deep(h1) { font-size: 1.6em; font-weight: 600; margin: 1.2em 0 0.5em; padding-bottom: 0.3em; border-bottom: 1px solid #eee; }
.yuque-doc :deep(h2) { font-size: 1.4em; font-weight: 600; margin: 1em 0 0.4em; padding-bottom: 0.2em; border-bottom: 1px solid #eee; }
.yuque-doc :deep(h3) { font-size: 1.2em; font-weight: 600; margin: 0.8em 0 0.3em; }
.yuque-doc :deep(p) { margin: 0.5em 0; }
.yuque-doc :deep(strong) { font-weight: 600; }
.yuque-doc :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
.yuque-doc :deep(th), .yuque-doc :deep(td) { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
.yuque-doc :deep(th) { background: #f6f8fa; font-weight: 600; }
.yuque-doc :deep(tr:nth-child(even)) { background: #fafbfc; }
.yuque-doc :deep(ul), .yuque-doc :deep(ol) { padding-left: 2em; margin: 0.5em 0; }
.yuque-doc :deep(li) { margin: 0.3em 0; }
.yuque-doc :deep(code) { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.88em; color: #d63384; }
.yuque-doc :deep(pre) { background: #f6f8fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; overflow-x: auto; margin: 1em 0; }
.yuque-doc :deep(pre code) { background: none; padding: 0; font-size: 0.85em; color: #1e293b; }
.yuque-doc :deep(blockquote) { margin: 1em 0; padding: 8px 16px; border-left: 4px solid #4f46e5; background: #f8fafc; color: #64748b; }
.yuque-doc :deep(td.change-highlight) { background: #fef3c7 !important; font-weight: 600; color: #92400e; }
.yuque-doc :deep(td.change-highlight) ~ td { background: #fffbeb; }
</style>