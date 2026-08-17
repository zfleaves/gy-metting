// API 基础配置（通过 Vite 代理转发到后端）
const BASE_URL = ''

// Token 管理
function getToken() {
  return localStorage.getItem('auth_token')
}

function setToken(token) {
  localStorage.setItem('auth_token', token)
}

function clearToken() {
  localStorage.removeItem('auth_token')
  localStorage.removeItem('auth_user')
}

export function getStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('auth_user') || 'null')
  } catch {
    return null
  }
}

async function request(url, options = {}) {
  const token = getToken()
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  const res = await fetch(`${BASE_URL}${url}`, {
    headers,
    ...options,
  })
  if (res.status === 401) {
    clearToken()
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    throw new Error('未登录或登录已过期')
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// 登录
export async function login(username, password) {
  const res = await request('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(res.token)
  localStorage.setItem('auth_user', JSON.stringify(res.user))
  return res.user
}

// 注册
export async function register(username, password) {
  const res = await request('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  })
  setToken(res.token)
  localStorage.setItem('auth_user', JSON.stringify(res.user))
  return res.user
}

// 退出
export function logout() {
  clearToken()
  window.location.href = '/login'
}

// 当前用户
export function getMe() {
  return request('/api/auth/me')
}

// 用户管理
export function listUsers() {
  return request('/api/users')
}

export function createUser(username, password, role) {
  return request('/api/users', {
    method: 'POST',
    body: JSON.stringify({ username, password, role }),
  })
}

export function deleteUser(userId) {
  return request(`/api/users/${userId}`, { method: 'DELETE' })
}

// 上传音频
export function uploadAudio(file) {
  const form = new FormData()
  form.append('file', file)
  const token = getToken()
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`${BASE_URL}/api/upload/audio`, {
    method: 'POST',
    body: form,
    headers,
  }).then(r => {
    if (r.status === 401) {
      clearToken()
      window.location.href = '/login'
      throw new Error('未登录')
    }
    return r.json()
  })
}

// 提交任务
export function submitTask(taskType, params = {}, name = '') {
  const query = new URLSearchParams({ task_type: taskType, ...params })
  if (name) query.set('name', name)
  return request(`/api/tasks?${query}`, { method: 'POST' })
}

// 查询任务
export function getTask(taskId) {
  return request(`/api/tasks/${taskId}`)
}

// 删除任务
export function deleteTask(taskId) {
  return request(`/api/tasks/${taskId}`, { method: 'DELETE' })
}

// 更新任务关联会议
export function updateTaskMeeting(taskId, meetingId) {
  return request(`/api/tasks/${taskId}/meeting`, {
    method: 'PATCH',
    body: JSON.stringify({ meeting_id: meetingId }),
  })
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

// 文字更正
export function addCorrection(wrong, correct) {
  return request('/api/tasks/corrections', {
    method: 'POST',
    body: JSON.stringify({ wrong, correct }),
  })
}

// 标记废话
export function addFluff(text) {
  return request('/api/tasks/fluff', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
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

// ============================================================
// 参考文档
// ============================================================

// 上传文档
export function uploadDocument(file) {
  const form = new FormData()
  form.append('file', file)
  const token = getToken()
  const headers = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  return fetch(`${BASE_URL}/api/documents/upload`, {
    method: 'POST',
    body: form,
    headers,
  }).then(r => {
    if (r.status === 401) { clearToken(); window.location.href = '/login'; throw new Error('未登录') }
    return r.json()
  })
}

// 语雀拉取
export function pullYuque(url, sourceId) {
  return request('/api/documents/yuque', {
    method: 'POST',
    body: JSON.stringify({ url, source_id: sourceId || null }),
  })
}

// 文档列表
export function listDocuments() {
  return request('/api/documents')
}

// 文档详情
export function getDocument(id) {
  return request(`/api/documents/${id}`)
}

// 删除文档
export function deleteDocument(id) {
  return request(`/api/documents/${id}`, { method: 'DELETE' })
}

// ============================================================
// 会议 & 业务背景
// ============================================================

// 创建会议
export function createMeeting(data) {
  return request('/api/meetings', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

// 更新会议
export function updateMeeting(id, data) {
  return request(`/api/meetings/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

// 会议列表
export function listMeetings() {
  return request('/api/meetings')
}

// 会议详情
export function getMeeting(id) {
  return request(`/api/meetings/${id}`)
}

// 删除会议
export function deleteMeeting(id) {
  return request(`/api/meetings/${id}`, { method: 'DELETE' })
}

// ============================================================
// 语雀来源
// ============================================================

export function listYuqueSources() {
  return request('/api/yuque-sources')
}

export function createYuqueSource(data) {
  return request('/api/yuque-sources', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function updateYuqueSource(id, data) {
  return request(`/api/yuque-sources/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteYuqueSource(id) {
  return request(`/api/yuque-sources/${id}`, { method: 'DELETE' })
}

// 拉取需求（通过来源 ID + 需求号）
export function pullYuqueRequirement(sourceId, requirementId) {
  return request(`/api/yuque-sources/${sourceId}/pull`, {
    method: 'POST',
    body: JSON.stringify({ requirement_id: requirementId }),
  })
}

// 拉取记录
export function listYuqueRecords() {
  return request('/api/yuque-records')
}

export function getYuqueRecord(id) {
  return request(`/api/yuque-records/${id}`)
}

export function deleteYuqueRecord(id) {
  return request(`/api/yuque-records/${id}`, { method: 'DELETE' })
}

export function rePullYuqueRecord(id) {
  return request(`/api/yuque-records/${id}/re-pull`, { method: 'POST' })
}