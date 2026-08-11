<template>
  <div class="users-page">
    <div class="page-header">
      <h1>用户管理</h1>
    </div>

    <div class="toolbar">
      <button class="btn-add" @click="showAdd = true">+ 新增用户</button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="user-list">
      <div v-for="u in users" :key="u.id" class="user-card">
        <div class="user-info">
          <span class="user-name">{{ u.username }}</span>
          <span class="user-role" :class="u.role">{{ roleLabel(u.role) }}</span>
        </div>
        <span class="user-time">{{ formatTime(u.created_at) }}</span>
        <button
          v-if="currentUser?.role === 'super_admin' && u.role !== 'super_admin'"
          class="btn-delete"
          @click="doDelete(u)"
        >删除</button>
      </div>
    </div>

    <!-- 新增用户弹窗 -->
    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal">
        <h3>新增用户</h3>
        <div class="field">
          <label>用户名</label>
          <input v-model="newUsername" type="text" placeholder="至少 2 个字符" />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="newPassword" type="password" placeholder="至少 4 个字符" />
        </div>
        <div class="field">
          <label>角色</label>
          <select v-model="newRole">
            <option value="user">普通用户</option>
            <option value="admin">管理员</option>
            <option v-if="currentUser?.role === 'super_admin'" value="super_admin">超级管理员</option>
          </select>
        </div>
        <div v-if="addError" class="error-msg">{{ addError }}</div>
        <div class="modal-actions">
          <button class="btn-cancel" @click="showAdd = false">取消</button>
          <button class="btn-save" @click="doCreate" :disabled="addLoading">创建</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, createUser, deleteUser, getStoredUser } from '../api.js'

const users = ref([])
const loading = ref(true)
const currentUser = ref(getStoredUser())
const showAdd = ref(false)
const newUsername = ref('')
const newPassword = ref('')
const newRole = ref('user')
const addLoading = ref(false)
const addError = ref('')

onMounted(async () => {
  try {
    users.value = await listUsers()
  } catch {
    // 忽略
  } finally {
    loading.value = false
  }
})

async function doCreate() {
  addError.value = ''
  if (!newUsername.value || !newPassword.value) {
    addError.value = '用户名和密码不能为空'
    return
  }
  addLoading.value = true
  try {
    await createUser(newUsername.value, newPassword.value, newRole.value)
    showAdd.value = false
    newUsername.value = ''
    newPassword.value = ''
    users.value = await listUsers()
  } catch (e) {
    addError.value = e.message
  } finally {
    addLoading.value = false
  }
}

async function doDelete(u) {
  if (!confirm(`确定删除用户「${u.username}」？`)) return
  try {
    await deleteUser(u.id)
    users.value = await listUsers()
  } catch (e) {
    alert(e.message)
  }
}

function roleLabel(r) {
  const map = { super_admin: '超级管理员', admin: '管理员', user: '普通用户' }
  return map[r] || r
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t + 'Z').toLocaleString('zh-CN')
}
</script>

<style scoped>
.users-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 24px;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h1 {
  font-size: 1.3rem;
  margin: 0;
  color: #1a1a2e;
}

.toolbar {
  margin-bottom: 16px;
}

.btn-add {
  padding: 8px 16px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
}

.loading {
  text-align: center;
  color: #94a3b8;
  padding: 40px;
}

.user-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-card {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  gap: 12px;
}

.user-info {
  display: flex;
  gap: 8px;
  align-items: center;
}

.user-name {
  font-weight: 500;
  color: #1e293b;
}

.user-role {
  font-size: 0.75rem;
  padding: 2px 8px;
  border-radius: 4px;
}

.user-role.super_admin { background: #fef2f2; color: #dc2626; }
.user-role.admin { background: #eef2ff; color: #4f46e5; }
.user-role.user { background: #f1f5f9; color: #64748b; }

.user-time {
  margin-left: auto;
  color: #94a3b8;
  font-size: 0.8rem;
}

.btn-delete {
  padding: 4px 12px;
  border: 1px solid #fecaca;
  background: #fff;
  color: #dc2626;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.8rem;
}

.btn-delete:hover {
  background: #fef2f2;
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  width: 360px;
}

.modal h3 {
  margin: 0 0 16px;
  color: #1e293b;
}

.field {
  margin-bottom: 12px;
}

.field label {
  display: block;
  font-size: 0.85rem;
  color: #64748b;
  margin-bottom: 4px;
}

.field input, .field select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 0.9rem;
  outline: none;
}

.field input:focus, .field select:focus {
  border-color: #4f46e5;
}

.error-msg {
  color: #dc2626;
  font-size: 0.8rem;
  margin-bottom: 8px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}

.btn-cancel {
  padding: 8px 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
}

.btn-save {
  padding: 8px 16px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}

.btn-save:disabled {
  opacity: 0.6;
}
</style>