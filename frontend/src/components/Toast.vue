<template>
  <Teleport to="body">
    <div class="toast-container">
      <transition-group name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="toast"
          :class="'toast-' + t.type"
          @click="remove(t.id)"
        >
          <span class="toast-icon">{{ icons[t.type] }}</span>
          <span class="toast-text">{{ t.message }}</span>
        </div>
      </transition-group>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../toast.js'

const { toasts, remove } = useToast()

const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' }
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}
.toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  font-size: 0.9rem;
  color: #334155;
  cursor: pointer;
  pointer-events: auto;
  max-width: 360px;
}
.toast-icon { font-size: 1rem; }
.toast-success { border-left: 4px solid #16a34a; }
.toast-error { border-left: 4px solid #dc2626; }
.toast-info { border-left: 4px solid #4f46e5; }
.toast-warning { border-left: 4px solid #d97706; }

.toast-enter-active { transition: all 0.3s ease; }
.toast-leave-active { transition: all 0.2s ease; }
.toast-enter-from { opacity: 0; transform: translateX(40px); }
.toast-leave-to { opacity: 0; transform: translateX(40px); }
</style>