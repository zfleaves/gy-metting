# 项目计划表

> 基于 [DESIGN.md §8 实施周期与里程碑](DESIGN.md) 制定
> 最后更新：2026-08-10

## 总览

| 阶段 | 预估工时 | 状态 | 开始 | 完成 |
|------|---------|------|------|------|
| [准备阶段](#准备阶段) | — | ✅ 完成 | 2026-08-10 | 2026-08-10 |
| [M1 基础能力搭建](#m1-基础能力搭建) | 3-5 天 | ⬜ 待开始 | — | — |
| [M2 参考文档接入](#m2-参考文档接入) | 3-5 天 | ⬜ 待开始 | — | — |
| [M3 AI 纪要生成](#m3-ai-纪要生成) | 3-5 天 | ⬜ 待开始 | — | — |
| [M4 输出与存储](#m4-输出与存储) | 2-3 天 | ⬜ 待开始 | — | — |
| [M5 前端界面](#m5-前端界面) | 3-5 天 | ⬜ 待开始 | — | — |

**总计：14-23 工作日（约 3-5 周）**，核心 API+CLI（M1-M4）可 2-3 周交付。

---

## 准备阶段

> 工程基础搭建，编码开始前完成。

- [x] 初始化 Python 项目骨架（`pyproject.toml`、`src/`、`main.py`）
- [x] 创建主 `requirements.txt`（FastAPI、faster-whisper、SQLAlchemy 等）
- [x] 创建 `data/` 目录结构（按 DESIGN.md §7.1）
- [x] 完善 `README.md`（项目介绍、快速开始、架构图引用）
- [x] 创建 `tests/` 目录占位

---

## M1 基础能力搭建

> 预估 3-5 天。项目初始化、ASR 模块集成、CLI 测试脚本、异步任务队列框架。

- [ ] 项目目录结构完善（`src/` 下各模块骨架）
- [ ] FastAPI 应用框架（`app.py`、路由注册、配置加载）
- [ ] 配置管理模块（从 `.env` 加载，pydantic-settings）
- [ ] ASR 模块 — Faster-Whisper 集成（`src/asr/whisper_engine.py`）
- [ ] ASR 模块 — 引擎抽象层（`src/asr/base.py`，预留 Qwen3-ASR-Flash）
- [ ] CLI 命令行工具（`cli.py`，任务提交、状态查询）
- [ ] 异步任务队列框架（`src/task/`，内存队列 + 状态机）
- [ ] 数据库初始化（SQLite WAL，SQLAlchemy 模型）
- [ ] 日志模块（结构化 JSON 日志）
- [ ] 单元测试：ASR 引擎、任务队列、配置加载

---

## M2 参考文档接入

> 预估 3-5 天。本地文档上传解析、语雀文档拉取与快照、HTML→Markdown 转换。

- [ ] 本地文档解析器（docx → `python-docx`）
- [ ] 本地文档解析器（pdf → `PyMuPDF`，含扫描件检测）
- [ ] 本地文档解析器（txt/md → 直接读取）
- [ ] 文档解析统一接口（`src/doc/parser.py`，`parse(file) → str`）
- [ ] 语雀拉取集成（调用 `scripts/yuque_pull.py`，合并到 `src/doc/yuque.py`）
- [ ] 文档快照存储（`src/doc/snapshot.py`，DESIGN.md §3.2.1）
- [ ] 参考文档 API 端点（上传、解析、快照查询）
- [ ] 单元测试：各格式解析、扫描件检测、快照读写

---

## M3 AI 纪要生成

> 预估 3-5 天。LLM 适配器抽象层、模板管理、上下文组装、大模型调用、双格式输出。

- [ ] LLM 适配器抽象层（`src/llm/adapter.py`，`chat(messages, ...)` 统一接口）
- [ ] OpenAI 兼容模式实现（`src/llm/openai_compat.py`）
- [ ] 提示词模板管理（`src/llm/templates/`，需求评审/技术评审/周会）
- [ ] 业务背景输入 + 自定义提示词支持
- [ ] 上下文组装引擎（`src/llm/context.py`，DESIGN.md §3.3.2）
- [ ] 三级截断策略（DESIGN.md §6.2，基于 tiktoken）
- [ ] 二阶段输出策略（先 Markdown 后 JSON，DESIGN.md §3.3.3）
- [ ] 防幻觉约束注入（DESIGN.md §6.1，5 条强制规则）
- [ ] LLM 重试与熔断（指数退避，最多 3 次，DESIGN.md §9）
- [ ] 单元测试：LLM 适配器、模板渲染、上下文组装修剪

---

## M4 输出与存储

> 预估 2-3 天。钉钉推送适配、数据持久化、SQLite WAL 配置、历史查询 API、健康检查。

- [ ] 钉钉 Webhook 推送（`src/output/dingtalk.py`，Markdown 消息）
- [ ] 输出适配器抽象层（`src/output/base.py`，预留多渠道）
- [ ] 数据持久化模块（`src/storage/db.py`，SQLAlchemy ORM）
- [ ] 会议元数据模型（Task、Meeting、Snapshot、Output）
- [ ] 历史查询 API（`GET /api/tasks`、`GET /api/tasks/{id}`）
- [ ] 健康检查端点（`/health`，DB 连接、ASR 状态、磁盘空间）
- [ ] 大字段文件存储（DB 存路径，文件存 `data/`）
- [ ] 单元测试：钉钉消息格式、数据库 CRUD、健康检查

---

## M5 前端界面

> 预估 3-5 天。Web 可视化界面。可跳过，优先交付 API+CLI。

- [ ] 前端技术选型（React/Vue/纯 HTML？待定）
- [ ] 会议表单页（主题、背景、模板选择、自定义提示词）
- [ ] 文件上传组件（音频、SRT、参考文档拖拽上传）
- [ ] 语雀链接输入 + 拉取进度展示
- [ ] 任务状态轮询 + 进度条
- [ ] 纪要结果预览页（Markdown 渲染 + JSON 切换）
- [ ] 历史会议列表 + 搜索
- [ ] 上下文占用指示器（已使用/总上限，DESIGN.md §6.2）

---

## 后续演进（V2+）

> 见 DESIGN.md §10，原型阶段不实现。

- [ ] 纪要待办自动生成钉钉待办任务
- [ ] 评审结果回写语雀文档
- [ ] 对接企业会议开放平台
- [ ] 用户权限控制
- [ ] 会议决策 RAG 知识库
- [ ] 扫描件 PDF OCR 支持
- [ ] WebSocket 实时推送任务进度