# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# 强制代码检索规则（本项目已启用CodeGraph本地代码图谱）
1. 任何代码查询、函数查找、调用链分析、架构梳理、接口溯源、变量检索需求，**必须优先调用codegraph工具**；
2. 禁止直接使用listDir、readFile、grep遍历读取项目大量文件；
3. 仅当codegraph返回无匹配/信息模糊时，才允许使用原生文件工具兜底；
4. 修改需求、评估代码改动影响范围时，全部依赖codegraph图谱分析依赖关系；
5. 回答代码相关问题时，先从codegraph获取结构化符号、调用关系，再输出内容。

## 项目概述

AI 智能会议纪要轻量化中台 — 目前处于**设计阶段**，尚未开始编码。完整设计方案见 `DESIGN.md`（V1.1, 2026-08-06）。

核心定位：部门级轻量化会议纪要中台，解决评审会议纪要编写耗时、决策遗漏、待办责任人不清晰等痛点。不依赖腾讯会议/钉钉企业版，模型无关架构。

## 生成提示词规则

所有提示词（系统提示词、会议模板、上下文规则）必须以 `DESIGN.md` 原文为准，标注章节号。设计文档未覆盖的细节标注【待确认】，不脑补。引用原则：原文照引不改写，跨章节标注关联。

详见 `DESIGN.md` §6.1 防幻觉约束（5 条强制规则）和 §3.3 提示词模板设计。

## 架构概要

**四层分层架构**（DESIGN.md §2.1）：
- **接入层**：CLI + HTTP API（FastAPI）
- **任务调度层**：异步任务队列（内存队列 + 数据库状态表）
- **核心能力层**：本地 ASR（Faster-Whisper 主选 / Qwen3-ASR-Flash 备选）、参考文档适配器（语雀 OpenAPI + 本地 docx/pdf/txt/md）、LLM 适配器（模型无关统一接口）、AI 纪要推理引擎
- **输出适配层**：钉钉机器人推送、Markdown + JSON 双格式输出
- **存储层**：SQLite WAL 模式（原型期）→ MySQL（后期）

**数据流**（§2.2）：任务提交 → 返回 task_id → 文件处理 & 参考文档拉取 → LLM 适配器 → 上下文组装 → 大模型调用 → Markdown + JSON 输出 → 可选钉钉推送 → 全量入库

**计划技术栈**：Python 3.10+, FastAPI, SQLite (WAL mode), Faster-Whisper (INT8), 前端待定

## 实施阶段

5 个里程碑（§8），总计 14-23 工作日：M1 基础能力 → M2 参考文档接入 → M3 AI 纪要生成 → M4 输出与存储 → M5 前端界面。若跳 M5 前端，核心 API+CLI 可在 2-3 周交付。

## 环境配置

所有配置集中在 `.env` 文件（基于 `DESIGN.md` V1.1），包含 10 个配置组：

| 配置组 | 关键变量 | 说明 |
|--------|---------|------|
| 服务基础 | `SERVER_HOST`, `SERVER_PORT`, `DEBUG` | FastAPI 服务配置 |
| LLM 大模型 | `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` | 支持 OpenAI 兼容模式，可切换 DeepSeek/通义千问/GLM |
| ASR 语音转写 | `ASR_ENGINE`, `WHISPER_MODEL_SIZE`, `WHISPER_COMPUTE_TYPE` | Faster-Whisper 本地离线（主选）或 Qwen3-ASR-Flash 云端（备选） |
| 语雀文档 | `YUQUE_API_TOKEN`, `YUQUE_SESSION`, `YUQUE_CTOKEN` | 语雀 OpenAPI 凭据 + Cookie（下载附件用） |
| 钉钉推送 | `DINGTALK_WEBHOOK_URL`, `DINGTALK_WEBHOOK_SECRET` | 选填，不填则不推送 |
| 数据库 | `DATABASE_URL`, `SQLITE_WAL_MODE` | 原型期 SQLite，后期切 MySQL |
| 文件存储 | `DATA_DIR`, `UPLOAD_DIR`, `SNAPSHOT_DIR`, `OUTPUT_DIR` | 本地存储路径 |
| 上传限制 | `MAX_AUDIO_SIZE_MB`, `MAX_DOC_SIZE_MB` | 音频 ≤200MB，文档 ≤20MB |
| 任务队列 | `TASK_TIMEOUT_MINUTES`, `MAX_CONCURRENT_TASKS` | 单任务超时 30min，默认并发 1 |
| 安全 | `SECRET_KEY`, `CORS_ORIGINS` | 加密密钥 + CORS 白名单 |

**⚠️ `.env` 包含真实 API Key 和 Token，切勿提交到版本控制或分享给外部。**

## 语雀文档拉取

两种方式拉取语雀 PRD 作为会议评审基线：

| 方式 | 命令 | 适用场景 |
|------|------|----------|
| Python 脚本 | `python scripts/yuque_pull.py --url "<语雀文档URL>"` | 功能完整，含 lakesheet 解码 + 快照保存 |
| MCP 工具 | `mcp__yuque__yuque_get_doc` | 快速预览 |
| Skill | 调用 `gy-meeting-yuque-pull` skill | Claude Code 内自动化拉取流程 |

**凭据**：从 `.env` 读取 `YUQUE_API_TOKEN` / `YUQUE_SESSION` / `YUQUE_CTOKEN`。

**脚本架构**：
- `scripts/yuque_sync.py` — 核心引擎（从 chongya-miniapp 复用，V2.1.0），负责语雀 OpenAPI 调用、增量同步、附件下载、lakesheet 解码
- `scripts/yuque_pull.py` — 会议场景适配层，在核心引擎之上封装 `pull_by_url()` / `pull_by_slug()` / `save_snapshot()` 三个接口

**快照位置**：`data/snapshots/yuque/{namespace}/{doc_id}_{slug}/`（含 `snapshot.md` + `snapshot_raw.json` + `meta.json`）

**依赖安装**：`pip install -r scripts/requirements.txt`（requests, PyYAML, xmindparser, markitdown）

## 数据目录结构

```
data/
├── meeting.db              ← SQLite 数据库（WAL 模式）
├── uploads/                ← 上传的音频和文档
├── snapshots/yuque/        ← 语雀文档快照（按 namespace/doc_id_slug 组织）
├── outputs/                ← AI 生成的纪要输出（Markdown + JSON）
└── temp/                   ← 临时文件
```

## 当前项目状态

- **阶段**：M1 基础能力已完成（2026-08-17），M2 参考文档待开始
- **现有资产**：`DESIGN.md`（唯一权威设计文档）、`DESIGN-REPORT.html`（可视化预览）、`.env`（配置模板）、语雀拉取脚本（从 chongya-miniapp 复用）；M1 完整后端（FastAPI + ASR + 任务队列）+ 前端（Vue3 + 中台管理布局 + 音频上传 + 转写结果展示 + 登录/注册 + 用户管理 + 任务删除）
- **Skill**：`.claude/skills/gy-meeting-yuque-pull/SKILL.md` — 语雀文档拉取自动化流程
- **本地配置**：`.claude/settings.local.json` — pip install / python 等命令权限
- **启动方式**：`python main.py`，后端直接 serve 前端（`http://localhost:8000`），无需单独启动 Vite