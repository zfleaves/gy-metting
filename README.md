# gy-meeting

**AI 智能会议纪要轻量化中台**

部门级轻量化会议纪要中台，解决评审会议纪要编写耗时、决策遗漏、待办责任人不清晰等痛点。不依赖腾讯会议/钉钉企业版，模型无关架构。

> 📖 完整设计方案：[DESIGN.md](DESIGN.md) | 可视化预览：[DESIGN-REPORT.html](DESIGN-REPORT.html)
> 📋 项目计划：[PROJECT-PLAN.md](PROJECT-PLAN.md)

## 快速开始

```bash
# 1. 安装依赖
pip install -e .[dev]

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入 LLM API Key、语雀 Token 等

# 3. 启动服务（M1 实现后可用）
python main.py
```

## 架构

```
接入层 (CLI + FastAPI)
  → 任务调度层 (异步队列)
    → 核心能力层 (ASR + 文档适配器 + LLM 适配器)
      → 输出适配层 (钉钉 + Markdown/JSON)
        → 存储层 (SQLite WAL)
```

详见 [DESIGN.md §2](DESIGN.md#2-整体架构设计)。

## 里程碑

| 阶段 | 工时 | 状态 |
|------|------|------|
| 准备阶段 | — | 🔄 进行中 |
| M1 基础能力 | 3-5天 | ⬜ |
| M2 参考文档接入 | 3-5天 | ⬜ |
| M3 AI 纪要生成 | 3-5天 | ⬜ |
| M4 输出与存储 | 2-3天 | ⬜ |
| M5 前端界面 | 3-5天 | ⬜ |

详见 [PROJECT-PLAN.md](PROJECT-PLAN.md)。

## 目录结构

```
gy-meeting/
├── DESIGN.md              ← 完整设计方案（11章）
├── PROJECT-PLAN.md        ← 项目计划
├── main.py                ← 入口
├── src/                   ← 源代码
│   ├── asr/               ← ASR 语音转写
│   ├── llm/               ← LLM 适配器 + 推理引擎
│   ├── doc/               ← 参考文档适配器
│   ├── task/              ← 异步任务队列
│   ├── output/            ← 输出适配（钉钉等）
│   ├── storage/           ← 数据持久化
│   └── api/               ← HTTP API 路由
├── scripts/               ← 工具脚本
│   ├── yuque_sync.py      ← 语雀同步核心引擎
│   └── yuque_pull.py      ← 语雀拉取适配层
├── tests/                 ← 测试
└── data/                  ← 本地数据（.gitignore 排除）
    ├── uploads/
    ├── snapshots/
    ├── outputs/
    └── temp/
```

## 技术栈

- **语言**：Python 3.10+
- **Web 框架**：FastAPI
- **ASR**：Faster-Whisper（主选）/ Qwen3-ASR-Flash（备选）
- **数据库**：SQLite WAL（原型期）→ MySQL（后期）
- **LLM**：模型无关，OpenAI 兼容模式接入 DeepSeek/通义千问/GLM