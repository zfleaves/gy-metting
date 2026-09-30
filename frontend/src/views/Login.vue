<template>
  <div class="login-page">
    <div class="login-card">
      <h1>gy-meeting</h1>
      <p class="subtitle">AI 智能会议纪要中台</p>
      <el-form @submit.prevent="isRegister ? doRegister() : doLogin()">
        <el-form-item label="用户名">
          <el-input v-model="username" type="text" placeholder="请输入用户名" autofocus />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-form-item v-if="isRegister" label="确认密码">
          <el-input v-model="confirmPassword" type="password" placeholder="请再次输入密码" show-password />
        </el-form-item>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          {{ isRegister ? '注册' : '登录' }}
        </el-button>
      </el-form>
      <p class="toggle-mode">
        {{ isRegister ? '已有账号？' : '没有账号？' }}
        <a href="#" @click.prevent="toggleMode">{{ isRegister ? '去登录' : '去注册' }}</a>
      </p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '../api.js'

const router = useRouter()
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')
const isRegister = ref(false)

function toggleMode() {
  isRegister.value = !isRegister.value
  error.value = ''
  username.value = ''
  password.value = ''
  confirmPassword.value = ''
}

async function doLogin() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await login(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}

async function doRegister() {
  if (!username.value || !password.value) {
    error.value = '请输入用户名和密码'
    return
  }
  if (password.value !== confirmPassword.value) {
    error.value = '两次密码不一致'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await register(username.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.message || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #1a1a2e;
  width: 100%;
}

.login-card {
  background: #fff;
  border-radius: 12px;
  padding: 40px;
  width: 360px;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}

.login-card h1 {
  text-align: center;
  color: #1a1a2e;
  font-size: 1.5rem;
  margin: 0 0 4px;
}

.subtitle {
  text-align: center;
  color: #94a3b8;
  font-size: 0.85rem;
  margin-bottom: 24px;
}

.error-msg {
  color: #dc2626;
  background: #fef2f2;
  padding: 8px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  margin-bottom: 12px;
}

.toggle-mode {
  text-align: center;
  margin-top: 16px;
  font-size: 0.85rem;
  color: #94a3b8;
}

.toggle-mode a {
  color: #4f46e5;
  text-decoration: none;
}
</style>