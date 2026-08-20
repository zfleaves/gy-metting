# 浏览器录音功能实现计划

## 目标
在现有上传页面上，增加浏览器录音功能。录音完成后自动命名、上传、走转写流程。

## 改动清单

### 1. 前端 `frontend/src/views/Upload.vue`（约 150 行）

**新增 UI 区域：**
- 录音按钮面板（「开始录音」/「停止」/「暂停」）
- 录音计时器（00:00 → 最大 30:00）
- 录音名称输入弹窗
- 录音状态提示（权限、错误、完成）

**新增状态变量：**
- `recordingState` — idle | recording | paused | done
- `recordDuration` — 录音秒数
- `recordChunks` — 录音数据块
- `recordName` — 录音名称
- `mediaStream` — 麦克风流
- `recorder` — MediaRecorder 实例

**新增函数：**
- `startRecording()` — 请求麦克风 → 创建 MediaRecorder → 开始录音
- `stopRecording()` — 停止录音 → 生成 Blob → 显示命名弹窗
- `pauseRecording()` / `resumeRecording()` — 暂停/继续
- `confirmUpload()` — 确认名称 → 上传 → 触发转写
- `cancelRecording()` — 释放麦克风资源

**边界处理：**
- 麦克风权限被拒 → 提示用户
- 浏览器不支持 → 隐藏录音按钮
- 录音超 30 分钟 → 自动停止
- 页面离开 → 释放资源

### 2. 前端 `frontend/src/api.js`（约 15 行）

**新增函数：**
- `uploadRecording(blob, filename)` — 将录音 Blob 包装为 File，调用现有 `uploadAudio()`

### 3. 后端 — 无需改动

现有 `POST /api/upload/audio` 支持 WebM/Opus 格式，后端 FFmpeg 自动解码。

---

## 预计工作量

| 模块 | 代码量 | 依赖 |
|------|--------|------|
| Upload.vue 模板 | ~60 行 | 无 |
| Upload.vue 脚本 | ~80 行 | MediaRecorder API |
| Upload.vue 样式 | ~40 行 | 无 |
| api.js | ~15 行 | 现有 uploadAudio |

**总计：约 200 行，纯前端改动**

## 执行顺序

1. `api.js` — 新增 `uploadRecording()` 函数
2. `Upload.vue` — 新增录音状态变量
3. `Upload.vue` — 新增录音函数（start/stop/pause/resume/confirm）
4. `Upload.vue` — 新增录音 UI 模板
5. `Upload.vue` — 新增录音 CSS 样式
6. 编译前端，测试