<template>
  <div id="app" :class="{
  'logged-in': currentUser,
  'logged-out': !currentUser,
  'detail-view': route.path.startsWith('/yuque-records/') || route.path.startsWith('/meeting/')
}">
    <!-- 登录页不显示布局 -->
    <template v-if="!currentUser">
      <router-view />
    </template>

    <!-- 后台布局 -->
    <template v-else>
      <aside class="sidebar">
        <div class="sidebar-header">
          <h1>gy-meeting</h1>
          <span class="version">v0.2</span>
        </div>
        <nav class="sidebar-nav">
          <router-link to="/" class="nav-item">
            <span class="nav-icon">📊</span> 工作台
          </router-link>
          <router-link to="/upload" class="nav-item">
            <span class="nav-icon">🎙️</span> 音频转写
          </router-link>
          <router-link to="/documents" class="nav-item">
            <span class="nav-icon">📄</span> 参考文档
          </router-link>
          <router-link to="/yuque-pull" class="nav-item">
            <span class="nav-icon">🦜</span> 语雀拉取
          </router-link>
          <router-link to="/yuque-records" class="nav-item">
            <span class="nav-icon">📋</span> 拉取记录
          </router-link>
          <router-link v-if="isAdmin" to="/users" class="nav-item">
            <span class="nav-icon">👥</span> 用户管理
          </router-link>
        </nav>
        <div class="sidebar-footer">
          <div class="user-info">
            <div class="avatar">{{ currentUser.username[0].toUpperCase() }}</div>
            <div class="user-detail">
              <div class="user-name">{{ currentUser.username }}</div>
              <div class="user-role">{{ roleLabel(currentUser.role) }}</div>
            </div>
          </div>
          <button class="btn-logout" @click="doLogout" title="退出登录">
            <span class="nav-icon">🚪</span> 退出
          </button>
        </div>
      </aside>
      <main class="main-content" :class="{ 'no-scroll': route.path.startsWith('/yuque-records/') || route.path.startsWith('/meeting/') }">
        <router-view />
      </main>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { getStoredUser, logout } from './api.js'

const router = useRouter()
const route = useRoute()

// 每次路由变化时重新读取用户状态
const currentUser = ref(getStoredUser())
watch(() => route.path, () => {
  currentUser.value = getStoredUser()
})

const isAdmin = computed(() => {
  return currentUser.value?.role === 'super_admin' || currentUser.value?.role === 'admin'
})

function roleLabel(r) {
  const map = { super_admin: '超级管理员', admin: '管理员', user: '普通用户' }
  return map[r] || r
}

function doLogout() {
  logout()
}
</script>

<style scoped>
#app {
  min-height: 100vh;
}

#app.logged-in {
  display: flex;
}
#app.detail-view.logged-in {
  height: 100vh;
}

#app.logged-out {
  display: block;
}

/* 侧边栏 */
.sidebar {
  width: 220px;
  background: #1e293b;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .sidebar {
    width: 60px;
  }

  .sidebar-header h1,
  .version,
  .nav-item span:not(.nav-icon),
  .user-detail,
  .btn-logout span:not(.nav-icon) {
    display: none;
  }

  .nav-item {
    justify-content: center;
    padding: 12px;
  }

  .nav-icon {
    margin: 0;
  }

  .btn-logout {
    justify-content: center;
    padding: 8px;
  }

  .user-info {
    justify-content: center;
  }

  .sidebar-footer {
    align-items: center;
  }
}

.sidebar-header {
  padding: 20px;
  border-bottom: 1px solid #334155;
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.sidebar-header h1 {
  color: #fff;
  font-size: 1.1rem;
  font-weight: 600;
  margin: 0;
}

.version {
  color: #64748b;
  font-size: 0.7rem;
}

.sidebar-nav {
  flex: 1;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  color: #94a3b8;
  text-decoration: none;
  border-radius: 8px;
  font-size: 0.9rem;
  transition: all 0.15s;
}

.nav-item:hover {
  background: #334155;
  color: #e2e8f0;
}

.nav-item.router-link-active {
  background: #4f46e5;
  color: #fff;
}

.nav-icon {
  font-size: 1.1rem;
  width: 24px;
  text-align: center;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid #334155;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: #4f46e5;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.user-detail {
  min-width: 0;
}

.user-name {
  color: #e2e8f0;
  font-size: 0.85rem;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  color: #64748b;
  font-size: 0.7rem;
}

.btn-logout {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: none;
  border: 1px solid #334155;
  border-radius: 6px;
  color: #94a3b8;
  font-size: 0.85rem;
  cursor: pointer;
  transition: all 0.15s;
  width: 100%;
}

.btn-logout:hover {
  border-color: #ef4444;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* 主内容区 */
.main-content {
  flex: 1;
  overflow-y: auto;
  min-width: 0;
  background: #f1f5f9;
}
.main-content.no-scroll {
  overflow: hidden;
}
</style>