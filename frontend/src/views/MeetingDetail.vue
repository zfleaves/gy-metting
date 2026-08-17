<template>
  <div class="detail-page">
    <div class="detail-topbar">
      <button class="btn-back" @click="goBack">← 返回列表</button>
      <div class="topbar-info">
        <strong>{{ meeting?.title }}</strong>
        <span v-if="meeting" class="doc-count">{{ meeting.snapshot_ids?.length || 0 }} 个文档</span>
      </div>
      <div class="topbar-actions">
        <button class="btn-edit" @click="goEdit">编辑</button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!meeting" class="loading">会议不存在</div>

    <template v-else>
      <!-- 业务背景 -->
      <div class="bg-section">
        <div class="bg-label">业务背景</div>
        <div class="bg-content">{{ meeting.background || '（无）' }}</div>
      </div>

      <!-- 左右分栏 -->
      <div class="split-pane">
        <!-- 左侧：文件列表 -->
        <div class="file-tree">
          <div class="tree-header">📄 关联文档（{{ meeting.snapshots?.length || 0 }}）</div>
          <div class="tree-list">
            <div
              v-for="(item, idx) in meeting.snapshots"
              :key="item.id || idx"
              class="tree-item"
              :class="{ active: selectedFileIdx === idx }"
              @click="selectFile(idx)"
            >
              <span class="file-icon">{{ item.source_type === 'yuque' ? '🦜' : '📄' }}</span>
              <span class="file-name">{{ item.title }}</span>
            </div>
            <div v-if="!meeting.snapshots?.length" class="empty-hint">暂无关联文档</div>
          </div>
        </div>

        <!-- 右侧：文件预览 -->
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
              <span class="preview-meta" v-if="previewMeta">{{ previewMeta.size }} 字</span>
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
import { getMeeting, getDocument } from '../api.js'
import { marked } from 'marked'

marked.setOptions({ breaks: true, gfm: true })

const route = useRoute()
const router = useRouter()
const meeting = ref(null)
const loading = ref(true)
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
  }
  catch { return previewContent.value }
})

onMounted(async () => {
  try {
    meeting.value = await getMeeting(route.params.id)
    if (meeting.value.snapshots?.length) {
      selectFile(0)
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
})

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}

function goBack() {
  router.push('/documents')
}

function goEdit() {
  router.push('/documents')
}

function selectFile(idx) {
  selectedFileIdx.value = idx
  const item = meeting.value.snapshots[idx]
  selectedFile.value = item
  if (!item?.id) { previewError.value = '文档不可预览'; return }

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
</script>

<style scoped>
.detail-page { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
.detail-topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-shrink: 0; }
.btn-back { padding: 6px 14px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #64748b; }
.btn-back:hover { border-color: #4f46e5; color: #4f46e5; }
.topbar-info { display: flex; align-items: center; gap: 8px; flex: 1; }
.topbar-info strong { font-size: 1.05rem; color: #1e293b; }
.topbar-actions { display: flex; gap: 8px; }
.doc-count { font-size: 0.78rem; color: #94a3b8; }
.btn-edit { padding: 6px 14px; border: 1px solid #e2e8f0; background: #fff; color: #4f46e5; border-radius: 6px; cursor: pointer; font-size: 0.82rem; }
.btn-edit:hover { background: #eef2ff; }
.loading { text-align: center; color: #94a3b8; padding: 60px 0; font-size: 0.95rem; }

/* 业务背景 */
.bg-section { padding: 12px 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; flex-shrink: 0; }
.bg-label { font-size: 0.78rem; color: #94a3b8; margin-bottom: 4px; }
.bg-content { font-size: 0.9rem; color: #334155; line-height: 1.6; white-space: pre-wrap; }

/* 分栏 */
.split-pane { display: flex; gap: 12px; flex: 1; min-height: 0; }
.file-tree { width: 280px; flex-shrink: 0; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; display: flex; flex-direction: column; overflow: hidden; }
.tree-header { padding: 10px 14px; font-size: 0.85rem; font-weight: 600; color: #1e293b; border-bottom: 1px solid #e2e8f0; background: #f8fafc; flex-shrink: 0; }
.tree-list { flex: 1; overflow-y: auto; padding: 4px 0; }
.tree-item { display: flex; align-items: center; gap: 8px; padding: 8px 14px; cursor: pointer; font-size: 0.84rem; color: #334155; border-left: 3px solid transparent; transition: all 0.1s; }
.tree-item:hover { background: #f8fafc; }
.tree-item.active { background: #eef2ff; border-left-color: #4f46e5; color: #4f46e5; }
.file-icon { flex-shrink: 0; font-size: 0.9rem; }
.file-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-hint { color: #94a3b8; font-size: 0.85rem; padding: 20px; text-align: center; }

/* 右侧预览 */
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

/* 语雀风格文档 */
.yuque-doc { padding: 40px 48px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 15px; line-height: 1.8; color: #262626; word-wrap: break-word; }
.yuque-doc :deep(h1) { font-size: 1.8em; font-weight: 600; margin: 1.2em 0 0.6em; padding-bottom: 0.3em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.yuque-doc :deep(h2) { font-size: 1.5em; font-weight: 600; margin: 1.2em 0 0.5em; padding-bottom: 0.2em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.yuque-doc :deep(h3) { font-size: 1.25em; font-weight: 600; margin: 1em 0 0.4em; color: #1a1a1a; }
.yuque-doc :deep(h4) { font-size: 1.1em; font-weight: 600; margin: 0.8em 0 0.3em; color: #1a1a1a; }
.yuque-doc :deep(p) { margin: 0.6em 0; }
.yuque-doc :deep(strong) { font-weight: 600; color: #1a1a1a; }
.yuque-doc :deep(a) { color: #4f46e5; text-decoration: none; }
.yuque-doc :deep(a:hover) { text-decoration: underline; }
.yuque-doc :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; display: block; overflow-x: auto; }
.yuque-doc :deep(th), .yuque-doc :deep(td) { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
.yuque-doc :deep(th) { background: #f6f8fa; font-weight: 600; color: #1a1a1a; }
.yuque-doc :deep(tr:nth-child(even)) { background: #fafbfc; }
.yuque-doc :deep(ul), .yuque-doc :deep(ol) { padding-left: 2em; margin: 0.5em 0; }
.yuque-doc :deep(li) { margin: 0.3em 0; }
.yuque-doc :deep(code) { font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace; background: #f0f0f0; padding: 2px 6px; border-radius: 3px; font-size: 0.88em; color: #d63384; }
.yuque-doc :deep(pre) { background: #f6f8fa; border: 1px solid #e2e8f0; border-radius: 6px; padding: 16px; overflow-x: auto; margin: 1em 0; }
.yuque-doc :deep(pre code) { background: none; padding: 0; font-size: 0.85em; color: #1e293b; line-height: 1.5; }
.yuque-doc :deep(blockquote) { margin: 1em 0; padding: 8px 16px; border-left: 4px solid #4f46e5; background: #f8fafc; color: #64748b; }
</style>