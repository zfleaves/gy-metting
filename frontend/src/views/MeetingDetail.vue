<template>
  <div class="detail-page">
    <div class="detail-topbar">
      <el-button size="small" @click="goBack">← 返回列表</el-button>
      <div class="topbar-info">
        <strong>{{ meeting?.title }}</strong>
        <span v-if="meeting" class="doc-count">{{ meeting.snapshot_ids?.length || 0 }} 个文档</span>
      </div>
      <div class="topbar-actions">
        <el-button size="small" @click="goEdit">编辑</el-button>
      </div>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-else-if="!meeting" class="loading">会议不存在</div>

    <template v-else>
      <div class="bg-section">
        <div class="bg-label">业务背景</div>
        <div class="bg-content">{{ meeting.background || '（无）' }}</div>
      </div>

      <div class="split-pane">
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
            <div class="preview-body" ref="previewBodyRef">
              <div class="yuque-doc" v-html="renderedContent" @click="onDocClick"></div>
            </div>

            <el-image-viewer
              v-if="lightboxVisible"
              :url-list="lightboxProxiedUrls"
              :initial-index="lightboxIdx"
              :hide-on-click-modal="false"
              @close="closeLightbox"
            />
          </template>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
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
const previewBodyRef = ref(null)

const lightboxVisible = ref(false)
const lightboxIdx = ref(0)
const lightboxImages = ref([])

const lightboxProxiedUrls = computed(() => {
  return lightboxImages.value.map(url => `/api/yuque-image-proxy?url=${encodeURIComponent(url)}`)
})

const renderedContent = computed(() => {
  if (!previewContent.value) return ''
  try {
    let html = marked.parse(previewContent.value)
    html = html.replace(/<img src="https:\/\/cdn\.nlark\.com([^"]+)"/g, (match, path) => {
      const origUrl = `https://cdn.nlark.com${path}`
      return `<img src="/api/yuque-image-proxy?url=${encodeURIComponent(origUrl)}" class="doc-img" data-img="${origUrl}"`
    })
    html = html.replace(
      /<td>(⚠️[^<]*)<\/td>/g,
      '<td class="change-highlight">$1</td>'
    )
    return html
  }
  catch { return previewContent.value }
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
    const imgRegex = /!\[.*?\]\((https?:\/\/[^\s)]+)\)|<img[^>]+src="(https?:\/\/[^"]+)"/g
    const imgs = []
    let m
    while ((m = imgRegex.exec(doc.content || '')) !== null) {
      imgs.push(m[1] || m[2])
    }
    lightboxImages.value = imgs
  }).catch(e => {
    previewError.value = '加载失败: ' + (e.message || '未知错误')
  }).finally(() => {
    previewLoading.value = false
  })
}

function onDocClick(e) {
  const img = e.target.closest('.doc-img')
  if (!img) return
  const idx = lightboxImages.value.indexOf(img.getAttribute('data-img'))
  if (idx >= 0) lightboxIdx.value = idx
  lightboxVisible.value = true
}

function closeLightbox() {
  lightboxVisible.value = false
}

function onKeydown(e) {
  if (e.key === 'Escape' && lightboxVisible.value) closeLightbox()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  loadMeeting()
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
})

async function loadMeeting() {
  try {
    meeting.value = await getMeeting(route.params.id)
    if (meeting.value.snapshots?.length) {
      selectFile(0)
    }
  } catch { /* ignore */ }
  finally { loading.value = false }
}
</script>

<style scoped>
.detail-page { padding: 20px 24px; height: 100%; display: flex; flex-direction: column; overflow: hidden; box-sizing: border-box; }
.detail-topbar { display: flex; align-items: center; gap: 16px; margin-bottom: 12px; flex-shrink: 0; }
.topbar-info { display: flex; align-items: center; gap: 8px; flex: 1; }
.topbar-info strong { font-size: 1.05rem; color: #1e293b; }
.topbar-actions { display: flex; gap: 8px; }
.doc-count { font-size: 0.78rem; color: #94a3b8; }
.loading { text-align: center; color: #94a3b8; padding: 60px 0; font-size: 0.95rem; }

.bg-section { padding: 12px 16px; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 12px; flex-shrink: 0; }
.bg-label { font-size: 0.78rem; color: #94a3b8; margin-bottom: 4px; }
.bg-content { font-size: 0.9rem; color: #334155; line-height: 1.6; white-space: pre-wrap; }

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
.yuque-doc :deep(h1) { font-size: 1.8em; font-weight: 600; margin: 1.2em 0 0.6em; padding-bottom: 0.3em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.yuque-doc :deep(h2) { font-size: 1.5em; font-weight: 600; margin: 1.2em 0 0.5em; padding-bottom: 0.2em; border-bottom: 1px solid #eee; color: #1a1a1a; }
.yuque-doc :deep(h3) { font-size: 1.25em; font-weight: 600; margin: 1em 0 0.4em; color: #1a1a1a; }
.yuque-doc :deep(p) { margin: 0.6em 0; }
.yuque-doc :deep(strong) { font-weight: 600; }
.yuque-doc :deep(a) { color: #4f46e5; text-decoration: none; }
.yuque-doc :deep(a:hover) { text-decoration: underline; }
.yuque-doc :deep(table) { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; display: block; overflow-x: auto; }
.yuque-doc :deep(th), .yuque-doc :deep(td) { border: 1px solid #d0d7de; padding: 8px 12px; text-align: left; }
.yuque-doc :deep(th) { background: #f6f8fa; font-weight: 600; }
.yuque-doc :deep(td.change-highlight) { background: #fef3c7 !important; font-weight: 600; color: #92400e; }
.yuque-doc :deep(.doc-img) { max-width: 100%; cursor: zoom-in; border: 1px solid #e2e8f0; border-radius: 4px; margin: 8px 0; }
</style>