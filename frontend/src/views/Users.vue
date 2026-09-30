<template>
  <div class="users-page">
    <div class="page-header">
      <h1>用户管理</h1>
    </div>

    <div class="toolbar">
      <el-button type="primary" @click="showAdd = true">+ 新增用户</el-button>
    </div>

    <div v-if="loading" class="loading">加载中...</div>

    <div v-else class="user-list">
      <el-card v-for="u in users" :key="u.id" shadow="never" class="user-card">
        <div class="user-card-inner">
          <div class="user-info">
            <span class="user-name">{{ u.username }}</span>
            <el-tag :type="tagType(u.role)" size="small" effect="plain">
              {{ roleLabel(u.role) }}
            </el-tag>
          </div>
          <span class="user-time">{{ formatTime(u.created_at) }}</span>
          <el-button
            v-if="currentUser?.role === 'super_admin' && u.role !== 'super_admin'"
            size="small"
            type="danger"
            plain
            @click="doDelete(u)"
          >删除</el-button>
        </div>
      </el-card>
    </div>

    <!-- 新增用户弹窗 -->
    <el-dialog v-model="showAdd" title="新增用户" width="420">
      <el-form>
        <el-form-item label="用户名">
          <el-input v-model="newUsername" placeholder="至少 2 个字符" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="newPassword" type="password" placeholder="至少 4 个字符" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="newRole" style="width: 100%">
            <el-option label="普通用户" value="user" />
            <el-option label="管理员" value="admin" />
            <el-option v-if="currentUser?.role === 'super_admin'" label="超级管理员" value="super_admin" />
          </el-select>
        </el-form-item>
        <div v-if="addError" class="error-msg">{{ addError }}</div>
      </el-form>
      <template #footer>
        <el-button @click="showAdd = false">取消</el-button>
        <el-button type="primary" @click="doCreate" :loading="addLoading">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { listUsers, createUser, deleteUser, getStoredUser } from '../api.js'
import { toast } from '../toast.js'

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

function tagType(role) {
  if (role === 'super_admin') return 'danger'
  if (role === 'admin') return 'primary'
  return 'info'
}

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
  try {
    await ElMessageBox.confirm(`确定删除用户「${u.username}」？`, '确认删除', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' })
    await deleteUser(u.id)
    users.value = await listUsers()
  } catch (e) {
    if (e !== 'cancel') toast.error(e.message)
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

.user-card { margin: 0; }
.user-card-inner {
  display: flex;
  align-items: center;
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

.user-time {
  margin-left: auto;
  color: #94a3b8;
  font-size: 0.8rem;
}

.error-msg {
  color: #dc2626;
  font-size: 0.8rem;
  margin-bottom: 8px;
}
</style>