/**
 * 简单 toast 通知系统
 * 使用方式: import { toast } from '../toast'; toast.success('成功');
 */
import { ref } from 'vue'

const toasts = ref([])
let nextId = 1

function add(message, type = 'info', duration = 2500) {
  const id = nextId++
  toasts.value.push({ id, message, type })
  setTimeout(() => remove(id), duration)
  return id
}

function remove(id) {
  const idx = toasts.value.findIndex(t => t.id === id)
  if (idx >= 0) toasts.value.splice(idx, 1)
}

export function useToast() {
  return {
    toasts,
    success: (msg) => add(msg, 'success'),
    error: (msg) => add(msg, 'error', 4000),
    info: (msg) => add(msg, 'info'),
    warning: (msg) => add(msg, 'warning', 3500),
    remove,
  }
}

export const toast = {
  success: (msg) => add(msg, 'success'),
  error: (msg) => add(msg, 'error', 4000),
  info: (msg) => add(msg, 'info'),
  warning: (msg) => add(msg, 'warning', 3500),
}