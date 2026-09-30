<template>
  <div class="detail-page">
    <div class="detail-topbar">
      <el-button size="small" @click="goBack">← 返回列表</el-button>
      <div class="topbar-info">
        <strong>{{ record?.requirement_id }}</strong>
        <span v-if="record?.source_name" class="source-tag">{{ record.source_name }}</span>
        <el-tag v-if="record" :type="statusType(record.status)" size="small" effect="dark">
          {{ statusLabel(record.status) }}
        </el-tag>
      </div>
      <div class="topbar-actions">
        <el-button size="small" :loading="repulling" @click="doRePull">
          🔄 重新拉取
        </el-button>
        <el-button size="small" type="danger" @click="doDelete">🗑 删除</el-button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!record" class="loading">记录不存在</div>

    <template v-else>
      <div class="stats-bar">
        <span>共 <b>{{ record.total }}</b> 个文档</span>
        <span class="stat-ok">✅ <b>{{ record.success }}</b> 成功</span>
        <span v-if="record.failed > 0" class="stat-fail">❌ <b>{{ record.failed }}</b> 失败</span>
        <span class="stat-time">拉取时间：{{ formatTime(record.created_at) }}</span>
      </div>

      <div class="split-pane">
        <div class="file-tree">
          <div class="tree-header">📄 拉取文件</div>
          <div class="tree-list">
            <div
              v-for="(item, idx) in record.results"
              :key="item.slug || idx"
              class="tree-item"
              :class="{ active: selectedFileIdx === idx, failed: item.status === 'failed' }"
              @click="selectFile(idx)"
            >
              <span class="file-icon">{{ item.status === 'ok' ? '📄' : '❌' }}</span>
              <span class="file-name">{{ item.title }}</span>
              <span v-if="item.status === 'failed'" class="file-error" :title="item.error">失败</span>
            </div>
          </div>
        </div>

        <div class="file-preview">
          <div v-if="selectedFile === null" class="preview-empty">
            请从左侧选择一个文件查看
          </div>
          <div v-else-if="previewLoading" class="preview-loading">
            <div class="spinner"></div>
            <span>加载文档内容...</span>
          </div>
          <div v-else-if="previewError" class="preview-error">
            {{ previewError }}
          </div>
          <template v-else>
            <div class="preview-header">
              <div class="preview-file-info">
                <span class="file-icon">📄</span>
                <span class="preview-filename">{{ selectedFile.title }}</span>
              </div>
              <span class="preview-meta" v-if="previewMeta">
                {{ previewMeta.size }} 字
              </span>
            </div>
            <div class="preview-body">
              <div class="yuque-doc" v-html="renderedContent"></div>
            </div>
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getYuqueRecord, deleteYuqueRecord, rePullYuqueRecord, getDocument } from '../api.js'
import { marked } from 'marked'
import { toast } from '../toast.js'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const router = useRouter()
const record = ref(null)
const loading = ref(true)
const repulling = ref(false)

const selectedFileIdx = ref(0)
const selectedFile = ref(null)

const previewContent = ref('')
const previewLoading = ref(false)
const previewError = ref('')
const previewMeta = ref(null)

const renderedContent = computed(() => {
  if (!previewContent.value) return ''
  try {
    let html = marked.parse(previewContent.value)
    html = html.replace(/<img src="https:\/\/cdn\.nlark\.com([^"]+)"/g, (match, path) => {
      const origUrl = `https://cdn.nlark.com${path}`
      return `<img src="/api/yuque-image-proxy?url=${encodeURIComponent(origUrl)}"`
    })
    return html
  } catch {
    return previewContent.value
  }
})

onMounted(async () => {
  try {
    record.value = await getYuqueRecord(route.params.id)
    const firstOk = record.value.results.findIndex(r => r.status === 'ok')
    if (firstOk >= 0) {
      selectFile(firstOk)
    } else {
      selectedFileIdx.value = -1
      selectedFile.value = null
    }
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

function goBack() {
  router.push('/yuque-records')
}

function selectFile(idx) {
  selectedFileIdx.value = idx
  const item = record.value.results[idx]
  selectedFile.value = item

  if (item.status !== 'ok' || !item.id) {
    previewContent.value = ''
    previewError.value = item.status === 'failed' ? (item.error || '拉取失败') : '文档不可预览'
    previewMeta.value = null
    return
  }

  previewLoading.value = true
  previewContent.value = ''
  previewError.value = ''
  previewMeta.value = null

  getDocument(item.id).then(doc => {
    previewContent.value = doc.content || '(无内容)'
    previewMeta.value = { size: (doc.content?.length || 0).toLocaleString() }
  }).catch(e => {
    previewError.value = '加载失败: ' + (e.message || '未知错误')
  }).finally(() => {
    previewLoading.value = false
  })
}

async function doRePull() {
  if (!record.value) return
  try {
    await ElMessageBox.confirm(`确定重新拉取「${record.value.requirement_id}」？`, '确认重新拉取', { confirmButtonText: '重新拉取', cancelButtonText: '取消', type: 'warning' })
    repulling.value = true
    await rePullYuqueRecord(route.params.id)
    record.value = await getYuqueRecord(route.params.id)
    const idx = Math.min(selectedFileIdx.value, record.value.results.length - 1)
    if (idx >= 0) selectFile(idx)
    toast.success('重新拉取完成！')
  } catch (e) {
    if (e !== 'cancel') toast.error('重新拉取失败: ' + (e.message || '未知错误'))
  } finally {
    repulling.value = false
  }
}

async function doDelete() {
  if (!record.value) return
  try {
    await ElMessageBox.confirm(`确定删除拉取记录「${record.value.requirement_id}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteYuqueRecord(route.params.id)
    router.push('/yuque-records')
  } catch (e) {
    if (e !== 'cancel') toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}
</script>

<style scoped>
.detail-page { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
.detail-topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-shrink: 0; }
.topbar-info { display: flex; align-items: center; gap: 8px; flex: 1; }
.topbar-info strong { font-size: 1.05rem; color: #1e293b; }
.topbar-actions { display: flex; gap: 8px; }
.source-tag { font-size: 0.75rem; background: #eef2ff; color: #4f46e5; padding: 2px 8px; border-radius: 4px; }
.loading { text-align: center; color: #94a3b8; padding: 60px 0; font-size: 0.95rem; }

.stats-bar { display: flex; gap: 16px; align-items: center; padding: 10px 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; font-size: 0.85rem; color: #64748b; flex-shrink: 0; }
.stats-bar b { font-weight: 600; color: #1e293b; }
.stat-ok b { color: #16a34a; }
.stat-fail b { color: #dc2626; }
.stat-time { margin-left: auto; color: #94a3b8; font-size: 0.8rem; }

.split-pane { display: flex; gap: 12px; flex: 1; min-height: 0; }
.file-tree { width: 280px; flex-shrink: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; display: flex; flex-direction: column; overflow: hidden; }
.tree-header { padding: 10px 14px; font-size: 0.85rem; font-weight: 600; color: #1e293b; border-bottom: 1px solid #e2e8f0; background: #f8fafc; flex-shrink: 0; }
.tree-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.tree-item { display: flex; align-items: center; gap: 8px; padding: 8px 14px; cursor: pointer; font-size: 0.84rem; color: #334155; border-left: 3px solid transparent; transition: all 0.1s; }
.tree-item:hover { background: #f8fafc; }
.tree-item.active { background: #eef2ff; border-left-color: #4f46e5; color: #4f46e5; }
.tree-item.failed { color: #dc2626; }
.file-icon { flex-shrink: 0; font-size: 0.9rem; }
.file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-error { font-size: 0.7rem; color: #dc2626; background: #fef2f2; padding: 1px 6px; border-radius: 3px; }

.file-preview { flex: 1; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; display: flex; flex-direction: column; overflow: hidden; min-width: 0; }
.preview-empty { display: flex; align-items: center; justify-content: center; flex: 1; color: #94a3b8; font-size: 0.9rem; }
.preview-loading { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 12px; color: #94a3b8; }
.preview-error { display: flex; align-items: center; justify-content: center; flex: 1; color: #dc2626; font-size: 0.9rem; padding: 20px; }
.spinner { width: 28px; height: 28px; border: 3px solid #e2e8f0; border-top-color: #4f46e5; border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
.preview-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 16px; border-bottom: 1px solid #e2e8f0; background: #f8fafc; flex-shrink: 0; }
.preview-file-info { display: flex; align-items: center; gap: 8px; }
.preview-filename { font-size: 0.85rem; font-weight: 500; color: #1e293b; }
.preview-meta { font-size: 0.78rem; color: #94a3b8; }
.preview-body { flex: 1; overflow-y: auto; padding: 0; }

.yuque-doc { padding: 40px 48px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.8; color: #262626; word-wrap: break-word; }
.yuque-doc :deep(h1) { font-size: 1.8em; font-weight: 600; margin: 1.2em 0 0.6em; padding-bottom: 0.3em; border-bottom: 1px solid #eee; }
.yuque-doc :deep(h2) { font-size: 1.5em; font-weight: 600; margin: 1.2em 0 0.5em; padding-bottom: 0.2em; border-bottom: 1px solid #eee; }
.yuque-doc :deep(h3) { font-size: 1.25em; font-weight: 600; margin: 1em 0 0.4em; }
.yuque-doc :deep(p) { margin: 0.6em 0; }
.yuque-doc :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; display: block; overflow-x: auto; }
.yuque-doc :deep(th), .yuque-doc :deep(td) { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
.yuque-doc :deep(th) { background: #f6f8fa; font-weight: 600; }
.yuque-doc :deep(code) { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.88em; color: #d63384; }
.yuque-doc :deep(pre) { background: #f6f8fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; overflow-x: auto; margin: 1em 0; }
.yuque-doc :deep(pre code) { background: none; padding: 0; font-size: 0.85em; color: #1e293b; }
.yuque-doc :deep(blockquote) { margin: 1em 0; padding: 8px 16px; border-left: 4px solid #4f46e5; background: #f8fafc; color: #64748b; }
</style>