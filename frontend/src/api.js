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