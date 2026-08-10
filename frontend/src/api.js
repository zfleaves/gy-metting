// API 基础配置（通过 Vite 代理转发到后端）
const BASE_URL = ''

async function request(url, options = {}) {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// 上传音频
export function uploadAudio(file) {
  const form = new FormData()
  form.append('file', file)
  return fetch(`${BASE_URL}/api/upload/audio`, {
    method: 'POST',
    body: form,
  }).then(r => r.json())
}

// 提交任务
export function submitTask(taskType, params = {}) {
  const query = new URLSearchParams({ task_type: taskType, ...params })
  return request(`/api/tasks?${query}`, { method: 'POST' })
}

// 查询任务
export function getTask(taskId) {
  return request(`/api/tasks/${taskId}`)
}

// 获取分段数据
export function getTaskSegments(taskId) {
  return request(`/api/tasks/${taskId}/segments`)
}

// 保存重点标记
export function saveHighlights(taskId, highlightedIndices) {
  return request(`/api/tasks/${taskId}/highlights`, {
    method: 'POST',
    body: JSON.stringify({ highlighted_indices: highlightedIndices }),
  })
}

// 获取重点标记
export function getHighlights(taskId) {
  return request(`/api/tasks/${taskId}/highlights`)
}

// 查询任务列表
export function listTasks({ status, task_type, limit = 20, offset = 0 } = {}) {
  const query = new URLSearchParams()
  if (status) query.set('status', status)
  if (task_type) query.set('task_type', task_type)
  query.set('limit', limit)
  query.set('offset', offset)
  return request(`/api/tasks?${query}`)
}

// 健康检查
export function healthCheck() {
  return request('/health')
}