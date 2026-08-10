"""
语雀文档拉取 — 会议纪要场景适配层
基于 yuque_sync.py 核心引擎，提供会议场景专用接口：

  - pull_by_url(url)          → 根据语雀文档 URL 拉取，返回 Markdown + 元数据
  - pull_by_slug(repo, slug)   → 根据知识库 + slug 拉取
  - save_snapshot(content, meta) → 保存快照到 data/snapshots/yuque/
  - 自动处理 lakesheet 解码（Sheet 类型文档 → Markdown 表格）

用法：
  python scripts/yuque_pull.py --url "https://gy19pay.yuque.com/laq5av/cdvo61/doc-slug"
  python scripts/yuque_pull.py --repo "laq5av/cdvo61" --slug "doc-slug"

环境变量（.env）：
  YUQUE_API_TOKEN   — 语雀 API Token（必填）
  YUQUE_SESSION     — _yuque_session Cookie（下载附件用，选填）
  YUQUE_CTOKEN      — yuque_ctoken Cookie（下载附件用，选填）
  SNAPSHOT_DIR      — 快照存储目录（默认 ./data/snapshots/yuque）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlsplit

# 确保脚本目录在 sys.path 中，以便导入 yuque_sync
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from yuque_sync import (
    YuqueClient,
    Config,
    try_decode_lakesheet,
    HTTP_TIMEOUT,
    ILLEGAL_NAME_CHARS,
)


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def _load_dotenv() -> Dict[str, str]:
    """从项目根目录 .env 加载环境变量（不覆盖已有环境变量）。"""
    env_file = _SCRIPT_DIR.parent / ".env"
    if not env_file.exists():
        return {}
    result = {}
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
                result[key] = val
    return result


def parse_yuque_url(url: str) -> Tuple[str, str]:
    """解析语雀文档 URL，返回 (namespace, slug)。

    支持格式：
      - https://<host>/<login>/<repo>/<slug>
      - https://<host>/<login>/<repo>?id=<doc_id>  （旧格式，用 doc_id 作 slug）

    namespace 格式：<login>/<repo>
    """
    parts = urlsplit(url.strip())
    if not parts.netloc:
        raise ValueError(f"无效的语雀 URL: {url}")

    path_segs = [p for p in parts.path.split("/") if p]
    if len(path_segs) < 3:
        raise ValueError(f"URL 需包含 <login>/<repo>/<slug> 三段路径: {url}")

    login, repo, slug = path_segs[0], path_segs[1], path_segs[2]
    namespace = f"{login}/{repo}"

    # 旧格式：?id=<doc_id> 作为 slug
    if parts.query:
        qs = parts.query
        m = re.search(r"id=(\d+)", qs)
        if m:
            slug = m.group(1)

    return namespace, slug


def sanitize_filename(name: str) -> str:
    """清洗文件名中的非法字符。"""
    name = ILLEGAL_NAME_CHARS.sub("_", name).strip().rstrip(".")
    return name or "untitled"


# ---------------------------------------------------------------------------
# 核心接口
# ---------------------------------------------------------------------------

def build_config(
    namespace: str,
    token: str,
    session: str = "",
    ctoken: str = "",
) -> Config:
    """构建 yuque_sync 的 Config 对象。"""
    host = "gy19pay.yuque.com"  # 默认，Config 会从 url 解析
    url = f"https://{host}/{namespace}"
    return Config(
        url=url,
        token=token,
        session=session or "",
        ctoken=ctoken or "",
        output="./data/temp_yuque",  # 临时目录，不影响快照
        exclude=[],
        attachment_types=[],
        embed_types=[],
    )


def pull_by_slug(
    namespace: str,
    slug: str,
    token: str,
    session: str = "",
    ctoken: str = "",
) -> Dict[str, Any]:
    """根据知识库 namespace 和文档 slug 拉取文档。

    返回:
      {
        "title": str,           # 文档标题
        "body": str,            # Markdown 正文（lakesheet 已解码）
        "body_raw": str,        # 原始 body（解码前）
        "slug": str,            # 文档 slug
        "doc_id": int,          # 语雀文档 ID
        "created_at": str,      # 创建时间 ISO
        "updated_at": str,      # 更新时间 ISO
        "namespace": str,       # 知识库 namespace
        "url": str,             # 文档完整 URL
      }
    """
    cfg = build_config(namespace, token, session, ctoken)
    client = YuqueClient(cfg)

    doc = client.get_doc(slug)
    body_raw = doc.get("body") or ""
    body = try_decode_lakesheet(body_raw, doc.get("title", ""))

    return {
        "title": doc.get("title", ""),
        "body": body,
        "body_raw": body_raw,
        "slug": doc.get("slug", slug),
        "doc_id": doc.get("id", 0),
        "created_at": doc.get("created_at", ""),
        "updated_at": doc.get("content_updated_at") or doc.get("updated_at", ""),
        "namespace": namespace,
        "url": f"https://gy19pay.yuque.com/{namespace}/{doc.get('slug', slug)}",
    }


def pull_by_url(
    url: str,
    token: str,
    session: str = "",
    ctoken: str = "",
) -> Dict[str, Any]:
    """根据语雀文档 URL 拉取文档。

    URL 格式：https://<host>/<login>/<repo>/<slug>
    """
    namespace, slug = parse_yuque_url(url)
    return pull_by_slug(namespace, slug, token, session, ctoken)


def save_snapshot(
    doc: Dict[str, Any],
    snapshot_dir: str = "",
    meeting_id: str = "",
) -> Path:
    """保存文档快照到本地。

    目录结构：
      {snapshot_dir}/
        {namespace}/
          {doc_id}_{slug}/
            snapshot.md          ← Markdown 正文（带元信息头）
            snapshot_raw.json    ← 原始 API 返回（含 body_raw）
            meta.json            ← 元数据

    返回快照目录路径。
    """
    if not snapshot_dir:
        snapshot_dir = os.environ.get("SNAPSHOT_DIR", "./data/snapshots/yuque")

    namespace = doc.get("namespace", "unknown")
    doc_id = doc.get("doc_id", 0)
    slug = doc.get("slug", "unknown")
    title = doc.get("title", "untitled")

    dir_name = sanitize_filename(f"{doc_id}_{slug}")
    snap_path = Path(snapshot_dir) / namespace / dir_name
    snap_path.mkdir(parents=True, exist_ok=True)

    # 拉取时间
    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    now_local = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ---- snapshot.md：带元信息头的 Markdown ----
    md_header = f"""# {title}

> 来源：语雀 `{doc["url"]}` (doc_id={doc_id})
> 拉取时间：{now_local}
> 快照目录：{snap_path}

---
"""
    md_content = md_header + doc["body"]
    (snap_path / "snapshot.md").write_text(md_content, encoding="utf-8")

    # ---- snapshot_raw.json：原始 API 返回 ----
    (snap_path / "snapshot_raw.json").write_text(
        json.dumps({
            "title": title,
            "slug": slug,
            "doc_id": doc_id,
            "namespace": namespace,
            "url": doc["url"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "body_raw": doc["body_raw"],
            "snapshot_at": now_str,
            "meeting_id": meeting_id or "",
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # ---- meta.json：元数据 ----
    (snap_path / "meta.json").write_text(
        json.dumps({
            "title": title,
            "doc_id": doc_id,
            "slug": slug,
            "namespace": namespace,
            "url": doc["url"],
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
            "snapshot_at": now_str,
            "meeting_id": meeting_id or "",
            "body_length": len(doc["body"]),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return snap_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    _load_dotenv()

    parser = argparse.ArgumentParser(
        description="语雀文档拉取 — 会议纪要场景适配",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--url", default="",
        help="语雀文档完整 URL（如 https://xxx.yuque.com/login/repo/slug）",
    )
    parser.add_argument(
        "--repo", default="",
        help="知识库 namespace（如 laq5av/cdvo61），与 --slug 配合使用",
    )
    parser.add_argument(
        "--slug", default="",
        help="文档 slug，与 --repo 配合使用",
    )
    parser.add_argument(
        "--token", default="",
        help="语雀 API Token（默认从环境变量 YUQUE_API_TOKEN 读取）",
    )
    parser.add_argument(
        "--session", default="",
        help="语雀 Session Cookie（默认从环境变量 YUQUE_SESSION 读取）",
    )
    parser.add_argument(
        "--ctoken", default="",
        help="语雀 CToken Cookie（默认从环境变量 YUQUE_CTOKEN 读取）",
    )
    parser.add_argument(
        "--snapshot-dir", default="",
        help="快照存储目录（默认从环境变量 SNAPSHOT_DIR 读取，或 ./data/snapshots/yuque）",
    )
    parser.add_argument(
        "--no-snapshot", action="store_true",
        help="不保存快照，仅输出到 stdout",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="以 JSON 格式输出结果",
    )
    args = parser.parse_args()

    # 获取凭据
    token = args.token or os.environ.get("YUQUE_API_TOKEN", "")
    session = args.session or os.environ.get("YUQUE_SESSION", "")
    ctoken = args.ctoken or os.environ.get("YUQUE_CTOKEN", "")

    if not token:
        print("ERROR: 缺少语雀 API Token。请设置 YUQUE_API_TOKEN 环境变量或通过 --token 传入。",
              file=sys.stderr)
        sys.exit(1)

    # 确定拉取方式
    try:
        if args.url:
            doc = pull_by_url(args.url, token, session, ctoken)
        elif args.repo and args.slug:
            doc = pull_by_slug(args.repo, args.slug, token, session, ctoken)
        else:
            print("ERROR: 请提供 --url 或 (--repo + --slug)", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: 拉取失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 保存快照
    snapshot_path = None
    if not args.no_snapshot:
        try:
            snapshot_path = save_snapshot(
                doc,
                snapshot_dir=args.snapshot_dir,
            )
        except Exception as e:
            print(f"WARNING: 快照保存失败: {e}", file=sys.stderr)

    # 输出结果
    if args.json:
        output = {
            "title": doc["title"],
            "body": doc["body"],
            "doc_id": doc["doc_id"],
            "slug": doc["slug"],
            "url": doc["url"],
            "snapshot_path": str(snapshot_path) if snapshot_path else None,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(doc["body"])
        if snapshot_path:
            print(f"\n---\n快照已保存: {snapshot_path}", file=sys.stderr)


if __name__ == "__main__":
    main()