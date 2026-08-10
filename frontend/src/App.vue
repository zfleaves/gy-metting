<template>
  <div id="app">
    <nav class="nav">
      <div class="nav-inner">
        <router-link to="/" class="logo">gy-meeting</router-link>
        <div class="nav-links">
          <router-link to="/">首页</router-link>
          <router-link to="/upload">上传</router-link>
        </div>
      </div>
    </nav>
    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
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

.nav-links a {
  color: #94a3b8;
  text-decoration: none;
  margin-left: 20px;
  font-size: 0.9rem;
  transition: color 0.2s;
}

.nav-links a:hover,
.nav-links a.router-link-active {
  color: #fff;
}

.main {
  min-height: calc(100vh - 52px);
  background: #f8fafc;
}
</style>