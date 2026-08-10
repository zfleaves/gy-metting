---
name: gy-meeting-yuque-pull
description: 从语雀拉取 PRD/需求文档作为会议评审基线。触发词："拉取语雀文档"、"从语雀拉取PRD"、"拉取需求文档"、"pull yuque doc"、"更新语雀快照"。适用于 gy-meeting 项目。
---

# GY Meeting — 语雀文档拉取

## 目标

从语雀拉取 PRD / 需求文档，保存为本地快照，作为会议纪要评审基线（DESIGN.md §3.2.1）。

## 适用场景

- 用户说"拉取语雀文档"、"从语雀拉取 PRD"、"拉取需求文档做评审"
- 准备会议前，需要将语雀 PRD 作为需求基线对照
- 会议结束后，需要保存 PRD 快照用于审计回溯

## 两种拉取方式

### 方式一：Python 脚本（推荐，功能完整）

```bash
# 按 URL 拉取
python scripts/yuque_pull.py --url "https://gy19pay.yuque.com/laq5av/cdvo61/<slug>"

# 按 namespace + slug 拉取
python scripts/yuque_pull.py --repo "laq5av/cdvo61" --slug "<slug>"

# 输出 JSON 格式（含元数据）
python scripts/yuque_pull.py --url "..." --json

# 不保存快照，仅输出内容
python scripts/yuque_pull.py --url "..." --no-snapshot
```

**功能**：
- 自动解码 lakesheet（Sheet 类型文档 → Markdown 表格）
- 保存三件套快照：`snapshot.md`（带元信息头）+ `snapshot_raw.json`（原始 API 返回）+ `meta.json`（元数据）
- 支持重试、错误处理
- 凭据从 `.env` 读取，无需每次传参

### 方式二：MCP 工具（快速预览）

使用 `mcp__yuque__yuque_get_doc` 直接获取文档内容，适合快速查看。
但 MCP 工具不支持 lakesheet 解码和本地快照保存，正式使用建议走 Python 脚本。

## 快照目录结构

```
data/snapshots/yuque/
  {namespace}/              ← 如 laq5av/cdvo61
    {doc_id}_{slug}/        ← 如 123456_my-prd-doc
      snapshot.md           ← Markdown 正文（带元信息头）
      snapshot_raw.json     ← 原始 API 返回（含 body_raw）
      meta.json             ← 元数据
```

## 凭据配置

凭据从项目根目录 `.env` 文件读取：

| 变量 | 用途 | 必填 |
|------|------|------|
| `YUQUE_API_TOKEN` | 语雀 API Token（只读） | ✅ |
| `YUQUE_SESSION` | `_yuque_session` Cookie（下载附件用） | 选填 |
| `YUQUE_CTOKEN` | `yuque_ctoken` Cookie（下载附件用） | 选填 |

## 关键约束

- **快照不可变**：拉取后快照内容不随语雀线上修改而变化，保证审计回溯（DESIGN.md §3.2.1）
- **Token 安全**：Token 仅存于 `.env`，不写入代码，不打印日志（DESIGN.md §3.2.1 安全约束）
- **HTML→Markdown**：语雀 API 返回的 body 已是 Markdown 格式，无需额外转换
- **lakesheet 解码**：Sheet 类型文档的 body 是私有 JSON+zlib 格式，`yuque_sync.py` 自动解码为 Markdown 表格
- **权限异常**：Token 失效、无权限、文档不存在时返回明确错误，不静默失败

## 会议场景集成

在会议纪要流程中（DESIGN.md §4），语雀拉取发生在第 3 步：

```
用户输入语雀文档链接
  → yuque_pull.py 拉取文档 + 保存快照
  → 快照内容注入 LLM 上下文（DESIGN.md §3.3.2 输入组装规则）
  → 作为【原始需求参考文档】参与纪要生成
```

## 与 chongya-miniapp 的差异

| 维度 | chongya-miniapp | gy-meeting |
|------|----------------|------------|
| 拉取粒度 | 按 SCPRO 需求号拉取全部文档 | 按单个文档 URL 拉取 |
| 文档类型 | PRD/系分/埋点/AI-Review 等 | PRD / 需求文档 |
| 本地目录 | `docs/chongya-prod/SCPRO-xxx/` | `data/snapshots/yuque/` |
| 空模板检测 | ✅ 三重检测 | ❌ 不适用（会议场景不删文档） |
| 代码改动生成 | ✅ git log + codegraph | ❌ |
| 核心引擎 | 同一个 `yuque_sync.py` | 同一个 `yuque_sync.py` |