<template>
  <div id="app">
    <nav class="nav" v-if="currentUser">
      <div class="nav-inner">
        <router-link to="/" class="logo">gy-meeting</router-link>
        <div class="nav-links">
          <router-link to="/">首页</router-link>
          <router-link to="/upload">上传</router-link>
          <router-link v-if="isAdmin" to="/users">用户管理</router-link>
        </div>
        <div class="nav-user">
          <span class="user-name">{{ currentUser.username }}</span>
          <span class="user-role-badge">{{ roleLabel(currentUser.role) }}</span>
          <button class="btn-logout" @click="doLogout">退出</button>
        </div>
      </div>
    </nav>
    <main class="main" :class="{ full: !currentUser }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { getStoredUser, logout } from './api.js'
import { useRouter } from 'vue-router'

const router = useRouter()
const currentUser = ref(getStoredUser())

const isAdmin = computed(() => {
  return currentUser.value?.role === 'super_admin' || currentUser.value?.role === 'admin'
})

function roleLabel(r) {
  const map = { super_admin: '超管', admin: '管理员', user: '用户' }
  return map[r] || r
}

function doLogout() {
  logout()
}
</script>

<style scoped>
.nav {
  background: #1a1a2e;
  padding: 0 20px;
  height: 52px;
  display: flex;
  align-items: center;
}

.nav-inner {
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.logo {
  color: #fff;
  font-weight: 600;
  font-size: 1.1rem;
  text-decoration: none;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-links a {
  color: #94a3b8;
  text-decoration: none;
  padding: 6px 12px;
  font-size: 0.9rem;
  border-radius: 6px;
  transition: color 0.2s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: #fff;
}

.nav-user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  color: #fff;
  font-size: 0.85rem;
}

.user-role-badge {
  font-size: 0.7rem;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255,255,255,0.15);
  color: #94a3b8;
}

.btn-logout {
  background: none;
  border: 1px solid #475569;
  color: #94a3b8;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 0.8rem;
  cursor: pointer;
  transition: all 0.15s;
}

.btn-logout:hover {
  border-color: #ef4444;
  color: #ef4444;
}

.main {
  min-height: calc(100vh - 52px);
  background: #f8fafc;
}

.main.full {
  min-height: 100vh;
}
</style>