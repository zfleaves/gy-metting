<template>
  <div class="preferences-page">
    <div class="page-header">
      <h1>⭐ 纪要偏好管理</h1>
      <p>上半区：未采纳的候选版本（每次生成自动保存）— 对比挑选后点击采纳<br>下半区：已采纳的偏好库 — 后续生成时可选用</p>
    </div>

    <!-- ====== 上半区：未采纳候选 ====== -->
    <section class="section">
      <div class="section-header">
        <h2>📋 未采纳候选（{{ unadopted.length }}）</h2>
        <button class="btn-refresh" @click="loadData">🔄 刷新</button>
      </div>

      <div v-if="loadingUnadopted" class="loading">加载中...</div>
      <div v-else-if="!unadopted.length" class="empty">暂无候选版本，生成纪要后会自动保存到这里</div>

      <div v-else class="candidate-list">
        <div
          v-for="(p, idx) in unadopted"
          :key="p.id"
          class="candidate-card"
          :class="{ selected: selectedId === p.id }"
          @click="selectPref(p)"
        >
          <div class="card-header">
            <span class="card-badge">#{{ unadopted.length - idx }}</span>
            <span class="card-type">{{ p.meeting_type }}</span>
            <span class="card-time">{{ formatTime(p.created_at) }}</span>
          </div>
          <div class="card-name">{{ p.name || '未命名' }}</div>
          <div v-if="p.notes" class="card-notes">📝 {{ p.notes }}</div>
          <div class="card-actions">
            <button class="btn-adopt" @click.stop="doAdopt(p)">✅ 采纳</button>
            <button class="btn-del-sm" @click.stop="doDelete(p)">🗑 删除</button>
          </div>
        </div>
      </div>
    </section>

    <!-- ====== 下半区：已采纳偏好 ====== -->
    <section class="section">
      <div class="section-header">
        <h2>✅ 已采纳偏好（{{ adopted.length }}）</h2>
      </div>

      <div v-if="loadingAdopted" class="loading">加载中...</div>
      <div v-else-if="!adopted.length" class="empty">暂无已采纳的偏好，从上方候选区采纳</div>

      <div v-else class="adopted-list">
        <div
          v-for="p in adopted"
          :key="p.id"
          class="adopted-card"
          :class="{ default: p.is_default }"
        >
          <div class="card-header">
            <span class="card-type">{{ p.meeting_type }}</span>
            <span v-if="p.is_default" class="default-badge">⭐ 默认</span>
            <span class="card-time">{{ formatTime(p.updated_at) }}</span>
          </div>
          <div class="card-name">{{ p.name || '未命名' }}</div>
          <div v-if="p.notes" class="card-notes">📝 {{ p.notes }}</div>

          <div class="card-preview">
            <pre class="preview-text">{{ (p.content || '').slice(0, 300) }}{{ (p.content || '').length > 300 ? '...' : '' }}</pre>
          </div>

          <div class="card-actions">
            <button class="btn-set-default" :disabled="p.is_default" @click="doSetDefault(p)">⭐ 设为默认</button>
            <button class="btn-edit" @click="doEditPref(p)">✏️ 编辑</button>
            <button class="btn-del-sm" @click="doDelete(p)">🗑 删除</button>
          </div>
        </div>
      </div>
    </section>

    <!-- 编辑弹窗 -->
    <div v-if="editItem" class="modal-overlay" @click.self="editItem = null">
      <div class="edit-modal">
        <div class="modal-header">
          <h3>编辑偏好</h3>
          <button class="modal-close" @click="editItem = null">✕</button>
        </div>
        <div class="modal-body">
          <div class="field">
            <label>名称</label>
            <input v-model="editForm.name" class="form-input" placeholder="如：需求评审-精简版" />
          </div>
          <div class="field">
            <label>会议类型</label>
            <select v-model="editForm.meeting_type" class="form-select">
              <option v-for="t in meetingTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div class="field">
            <label>备注</label>
            <textarea v-model="editForm.notes" class="form-textarea" rows="2" placeholder="偏好说明"></textarea>
          </div>
          <div class="field">
            <label>偏好内容（Markdown）</label>
            <textarea v-model="editForm.content" class="form-textarea code" rows="10"></textarea>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-cancel" @click="editItem = null">取消</button>
          <button class="btn-save-modal" @click="doSaveEdit" :disabled="saving">{{ saving ? '保存中...' : '保存' }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listPreferences, updatePreference, deletePreference, createPreference } from '../api.js'
import { toast } from '../toast.js'

const meetingTypes = ['通用', '需求评审', '技术评审', '周会']

const unadopted = ref([])
const adopted = ref([])
const loadingUnadopted = ref(true)
const loadingAdopted = ref(true)
const selectedId = ref(null)

// 编辑弹窗
const editItem = ref(null)
const editForm = ref({ name: '', meeting_type: '通用', notes: '', content: '' })
const saving = ref(false)

onMounted(() => { loadData() })

async function loadData() {
  loadingUnadopted.value = true
  loadingAdopted.value = true
  try {
    const [unadoptedRes, adoptedRes] = await Promise.all([
      listPreferences({ adopted: 0 }),
      listPreferences({ adopted: 1 }),
    ])
    unadopted.value = unadoptedRes.preferences || []
    adopted.value = adoptedRes.preferences || []
  } catch (e) {
    toast.error('加载偏好失败: ' + (e.message || '未知错误'))
  } finally {
    loadingUnadopted.value = false
    loadingAdopted.value = false
  }
}

function selectPref(p) {
  selectedId.value = selectedId.value === p.id ? null : p.id
}

async function doAdopt(p) {
  try {
    await updatePreference(p.id, { adopt: true, name: p.name || `偏好-${p.meeting_type}-${formatTime(p.created_at)}` })
    toast.success('已采纳！')
    loadData()
  } catch (e) {
    toast.error('采纳失败: ' + (e.message || '未知错误'))
  }
}

async function doSetDefault(p) {
  try {
    await updatePreference(p.id, { set_default: true })
    toast.success('已设为默认偏好')
    loadData()
  } catch (e) {
    toast.error('设置失败: ' + (e.message || '未知错误'))
  }
}

async function doDelete(p) {
  if (!confirm(`确定删除「${p.name || '未命名'}」？`)) return
  try {
    await deletePreference(p.id)
    toast.success('已删除')
    loadData()
  } catch (e) {
    toast.error('删除失败: ' + (e.message || '未知错误'))
  }
}

function doEditPref(p) {
  editItem.value = p
  editForm.value = {
    name: p.name || '',
    meeting_type: p.meeting_type || '通用',
    notes: p.notes || '',
    content: p.content || '',
  }
}

async function doSaveEdit() {
  if (!editItem.value) return
  saving.value = true
  try {
    await updatePreference(editItem.value.id, editForm.value)
    toast.success('保存成功')
    editItem.value = null
    loadData()
  } catch (e) {
    toast.error('保存失败: ' + (e.message || '未知错误'))
  } finally {
    saving.value = false
  }
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<style scoped>
.preferences-page { padding: 24px; }
.page-header { margin-bottom: 24px; }
.page-header h1 { font-size: 1.3rem; color: #1e293b; margin: 0 0 4px; }
.page-header p { color: #94a3b8; font-size: 0.8rem; margin: 0; line-height: 1.5; }

.section { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px; margin-bottom: 24px; }
.section-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 16px; }
.section-header h2 { font-size: 1rem; color: #1e293b; margin: 0; }
.btn-refresh { padding: 4px 12px; border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; cursor: pointer; font-size: 0.78rem; color: #64748b; }
.btn-refresh:hover { border-color: #4f46e5; color: #4f46e5; }

.loading { text-align: center; padding: 24px; color: #94a3b8; }
.empty { text-align: center; padding: 24px; color: #94a3b8; font-size: 0.85rem; }

/* 候选卡片 */
.candidate-list { display: flex; flex-direction: column; gap: 8px; }
.candidate-card, .adopted-card { border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; cursor: pointer; transition: all 0.15s; }
.candidate-card:hover { border-color: #4f46e5; }
.candidate-card.selected { border-color: #4f46e5; background: #eef2ff; }
.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.card-badge { font-size: 0.75rem; background: #e2e8f0; color: #64748b; padding: 1px 8px; border-radius: 3px; font-weight: 600; }
.card-type { font-size: 0.72rem; background: #eef2ff; color: #4f46e5; padding: 1px 6px; border-radius: 3px; }
.card-time { font-size: 0.72rem; color: #94a3b8; margin-left: auto; }
.card-name { font-size: 0.9rem; color: #1e293b; font-weight: 500; margin-bottom: 4px; }
.card-notes { font-size: 0.78rem; color: #d97706; margin-bottom: 6px; }
.card-actions { display: flex; gap: 6px; margin-top: 8px; }
.card-actions button { padding: 4px 10px; border: 1px solid #e2e8f0; background: #fff; border-radius: 4px; cursor: pointer; font-size: 0.75rem; color: #64748b; }
.card-actions button:hover { border-color: #4f46e5; color: #4f46e5; }
.card-preview { margin-top: 8px; }
.preview-text { font-size: 0.75rem; color: #64748b; background: #f8fafc; padding: 8px; border-radius: 4px; max-height: 120px; overflow-y: auto; margin: 0; font-family: 'SFMono-Regular', Consolas, monospace; line-height: 1.4; }

/* 已采纳卡片 */
.adopted-card { cursor: default; }
.adopted-card.default { border-color: #d97706; background: #fffbeb; }
.default-badge { font-size: 0.7rem; background: #d97706; color: #fff; padding: 1px 6px; border-radius: 3px; }
.btn-adopt { background: #16a34a !important; color: #fff !important; border-color: #16a34a !important; }
.btn-adopt:hover { background: #15803d !important; }
.btn-set-default { background: #d97706 !important; color: #fff !important; border-color: #d97706 !important; }
.btn-set-default:disabled { opacity: 0.4; cursor: not-allowed !important; }
.btn-del-sm:hover { border-color: #dc2626 !important; color: #dc2626 !important; }
.btn-edit:hover { border-color: #4f46e5 !important; color: #4f46e5 !important; }

/* 弹窗 */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 100; }
.edit-modal { background: #fff; border-radius: 12px; width: 680px; max-width: 95vw; max-height: 85vh; display: flex; flex-direction: column; box-shadow: 0 20px 60px rgba(0,0,0,0.3); }
.modal-header { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid #e2e8f0; }
.modal-header h3 { margin: 0; font-size: 1rem; color: #1e293b; }
.modal-close { width: 32px; height: 32px; border: none; background: none; font-size: 1.2rem; cursor: pointer; color: #94a3b8; border-radius: 6px; }
.modal-close:hover { background: #e2e8f0; color: #1e293b; }
.modal-body { padding: 20px; overflow-y: auto; flex: 1; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 20px; border-top: 1px solid #e2e8f0; }
.field { margin-bottom: 14px; }
.field label { display: block; font-size: 0.82rem; color: #64748b; margin-bottom: 4px; font-weight: 500; }
.form-input, .form-select, .form-textarea { width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 0.85rem; outline: none; box-sizing: border-box; }
.form-input:focus, .form-select:focus, .form-textarea:focus { border-color: #4f46e5; }
.form-textarea.code { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.78rem; line-height: 1.5; resize: vertical; }
.btn-cancel { padding: 8px 20px; border: 1px solid #e2e8f0; background: #fff; border-radius: 6px; cursor: pointer; font-size: 0.85rem; color: #64748b; }
.btn-cancel:hover { border-color: #dc2626; color: #dc2626; }
.btn-save-modal { padding: 8px 20px; background: #4f46e5; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 0.85rem; }
.btn-save-modal:hover { background: #4338ca; }
.btn-save-modal:disabled { opacity: 0.6; cursor: not-allowed; }
</style>