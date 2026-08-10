#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
语雀知识库增量同步工具（yuque_sync）

把语雀云端知识库增量同步到本地（weknora 数据源模式）：
  Step1：按目录树（TOC）下载所有 markdown 文档，保留目录结构，按 content_updated_at 时间戳做增量。
  Step2：遍历所有 md，下载 --attachment-types 指定类型的附件文件到文档同目录
         （附件文件名带文档的时间戳后缀，便于增量管理），并把原文档引用地址改写为本地相对路径。
  Step3：遍历所有 md，对 --embed-types 指定类型的「本地附件引用」，把附件转成 markdown，
         用转换后的内容替换原引用（删除引用、原地嵌入），并删除附件原始文件。

跨平台（Windows/macOS/Linux），单文件，依赖 requests + PyYAML + xmindparser + markitdown
（+ LibreOffice 处理 .doc，系统级）。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
import zlib
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlparse, urlsplit

try:
    import requests
    from requests.adapters import HTTPAdapter
    try:
        from urllib3.util.retry import Retry
    except ImportError:  # pragma: no cover
        from requests.packages.urllib3.util.retry import Retry  # type: ignore
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "缺少依赖 requests，请先执行: pip install -r requirements.txt\n"
    )
    raise

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.stderr.write(
        "缺少依赖 PyYAML，请先执行: pip install -r requirements.txt\n"
    )
    raise


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 版本号：每次发版更新此处。用 `yuque-sync --version` 查询当前已安装版本。
__version__ = "2.1.0"

DEFAULT_OUTPUT_DIR = "./downloads"
MANIFEST_FILENAME = "manifest.json"
HTTP_TIMEOUT = 30
# 文件名中非法字符（跨平台）
ILLEGAL_NAME_CHARS = re.compile(r'[\\/:*?"<>|\n\r\t]')
# 时间戳行尾正则：匹配 <title>-<digits>.md（Step1 文档）或 <stem>-<digits>.<ext>（Step2 附件）
DOC_TS_RE = re.compile(r"^(?P<title>.+)-(?P<ts>\d{10})\.md$")
# 图片扩展名（不算附件，不下载、不嵌入）
IMAGE_EXTS = {"png", "jpg", "jpeg", "gif", "bmp", "webp", "svg", "ico", "tiff", "tif"}
# 网页类扩展名（不是附件）
WEB_EXTS = {"html", "htm", "php", "asp", "aspx", "jsp", "do", "action"}
# Step2 默认下载的附件类型
DEFAULT_ATTACHMENT_TYPES = ["docx", "pdf", "xls", "xlsx", "doc", "xmind", "pptx", "ppt"]
# Step3 默认嵌入转换的类型
DEFAULT_EMBED_TYPES = ["xmind"]
# 远程附件链接正则：[name](http(s)://...)，Step2 从中下载附件
REMOTE_LINK_RE = re.compile(r"\[(?P<name>[^\]]+)\]\((?P<url>https?://[^)]+)\)", re.IGNORECASE)
# 本地附件链接正则：[name](本地路径)，Step3 从中读取已下载文件做嵌入转换
# 本地路径不含 ://（排除远程链接），可为相对/绝对路径
LOCAL_LINK_RE = re.compile(r"\[(?P<name>[^\]]+)\]\((?P<url>(?!https?://)[^)]+)\)", re.IGNORECASE)
# 附件 URL 内的上传时间戳（毫秒）：形如 /1782109285319-xxxx.ext
ATTACH_URL_TS_RE = re.compile(r"/(\d{13})-")
# 附件嵌入块标记（Step3 转换内容替换原引用时使用）
ATTACH_BLOCK_BEGIN = "<!-- attachment-inline: {name} -->"
ATTACH_BLOCK_END = "<!-- attachment-inline-end -->"


# ---------------------------------------------------------------------------
# 日志
# ---------------------------------------------------------------------------

LOG = logging.getLogger("yuque_sync")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------

def sanitize_name(name: str) -> str:
    """清洗文件/目录名中的非法字符。"""
    name = ILLEGAL_NAME_CHARS.sub("_", name).strip().rstrip(".")
    return name or "untitled"


def iso_to_timestamp(iso_str: str) -> int:
    """ISO-8601 时间字符串 -> Unix 秒级时间戳。

    语雀返回形如 '2026-06-22T06:24:03.000Z'。
    """
    if not iso_str:
        return 0
    s = iso_str.strip()
    # 兼容带/不带时区后缀
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # 兜底：按 UTC 解析
        dt = datetime.strptime(iso_str[:19], "%Y-%m-%dT%H:%M:%S").replace(
            tzinfo=timezone.utc
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


# ---------------------------------------------------------------------------
# 语雀表格（lakesheet）解码：把私有 JSON + zlib 格式还原成 markdown 表格
# ---------------------------------------------------------------------------
# 语雀对 sheet 类型文档，API 的 body 直接返回 lakesheet JSON：
#   {"format":"lakesheet","version":"x","sheet":"<zlib 压缩的字符串>", ...}
# sheet 字段是 latin1 编码的 zlib 压缩字节（magic 78 9c），解压后是内层 JSON：
#   [{"name":"工作表名","data":{"<行号>":{"<列号>":{"v":<单元格值>}}}, ...}]
# 客户端必须自己解码，语雀 API 没有服务端转 markdown 的能力（已验证）。

# lakesheet 判定前缀（body 开头）
_LAKESHEET_PREFIX = '{"format":"lakesheet"'
# Excel 日期序列号起点（1900-01-01 的序列号是 1，但 Excel 有 1900 闰年 bug，用 1899-12-30 作基准）
_EXCEL_EPOCH = datetime(1899, 12, 30)
# Excel 时间戳数值范围（超出此范围视为普通数字，避免误判大数字为日期）
_EXCEL_DATE_MIN = 3000
_EXCEL_DATE_MAX = 60000


def _excel_serial_to_date(value: float) -> str:
    """Excel 日期序列号 -> 'YYYY-MM-DD' 或 'YYYY-MM-DD HH:MM:SS' 字符串。"""
    try:
        # 整数部分是天数，小数部分是天内时间
        days = int(value)
        frac = value - days
        dt = _EXCEL_EPOCH + timedelta(days=days)
        if frac > 0:
            seconds = int(round(frac * 86400))
            dt = dt + timedelta(seconds=seconds)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(value)


def _format_cell_value(v: Any) -> str:
    """把 lakesheet 单元格的 v 值格式化成 markdown 单元格文本。

    支持的单元格类型：
      - str / int / float：直接转字符串（数字看起来像 Excel 日期则转日期）
      - dict（带 class 字段的富类型）：
        - select  -> value 列表 join
        - checkbox -> [x] / [ ]
        - link    -> [text](url)
        - image   -> ![name](src)
        - date    -> 格式化日期串
        - 其他    -> 尽量取 value/text/name 字段，失败则 JSON 串兜底

    语雀日期存储格式（实测）：大整数 = Excel序列号 × 86400（天转秒），
    如 3866140800 = 44747 × 86400 → 2022-07-05。少数情况是裸 Excel 序列号（5位数）。
    """
    if v is None:
        return ""
    # 普通类型
    if isinstance(v, str):
        return v.replace("|", "\\|").replace("\n", " ").strip()
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, (int, float)):
        num = float(v)
        # 情况1：大整数（Excel序列号 × 86400），如 3866140800
        if num >= 86400 and num == int(num) and num % 86400 == 0:
            serial = num / 86400
            if _EXCEL_DATE_MIN <= serial <= _EXCEL_DATE_MAX:
                return _excel_serial_to_date(serial)
        # 情况2：裸 Excel 序列号（5 位数），如 44747
        if _EXCEL_DATE_MIN <= num <= _EXCEL_DATE_MAX and num == int(num):
            return _excel_serial_to_date(num)
        return str(v)
    # 复杂类型（dict）
    if isinstance(v, dict):
        cls = v.get("class") or v.get("type") or ""
        if cls == "select":
            val = v.get("value")
            if isinstance(val, list):
                return ",".join(str(x) for x in val)
            return str(val) if val is not None else ""
        if cls == "checkbox":
            return "[x] " if v.get("value") or v.get("checked") else "[ ] "
        if cls == "link":
            text = v.get("text") or v.get("name") or v.get("value") or ""
            url = v.get("url") or v.get("src") or ""
            return f"[{text}]({url})" if url else str(text)
        if cls == "image":
            name = v.get("name") or v.get("alt") or "image"
            src = v.get("src") or v.get("url") or ""
            return f"![{name}]({src})" if src else f"[图片:{name}]"
        if cls == "date":
            val = v.get("value")
            if val is not None:
                if isinstance(val, (int, float)):
                    num = float(val)
                    if num >= 86400 and num == int(num) and num % 86400 == 0:
                        return _excel_serial_to_date(num / 86400)
                    return _excel_serial_to_date(num)
                return str(val)
            return str(v.get("text") or "")
        # 兜底：优先取 value/text，再退到 name，最后 JSON 串
        for key in ("value", "text", "name"):
            if key in v and v[key] is not None:
                s = str(v[key])
                return s.replace("|", "\\|").replace("\n", " ").strip()
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, list):
        return ",".join(_format_cell_value(x) for x in v)
    return str(v)


def _sheet_to_markdown(sheet: Dict[str, Any]) -> str:
    """单个 sheet 对象 -> markdown 表格字符串。

    sheet 结构：{name, data:{"<行号>":{"<列号>":{v:值}}}, mergeCells:{...}}
    """
    name = str(sheet.get("name") or "工作表").strip() or "工作表"
    data = sheet.get("data") or {}
    if not data:
        return f"## {name}\n\n*(空表格)*\n"

    # 收集所有出现的行号和列号（data 的 key 是字符串数字）
    row_keys = sorted(int(r) for r in data.keys() if str(r).isdigit())
    if not row_keys:
        return f"## {name}\n\n*(无有效行)*\n"

    # 列范围：遍历所有行，取最大列号
    col_set = set()
    for r in data.values():
        if isinstance(r, dict):
            for c in r.keys():
                if str(c).isdigit():
                    col_set.add(int(c))
    if not col_set:
        return f"## {name}\n\n*(无有效列)*\n"
    col_keys = sorted(col_set)

    lines = [f"## {name}", ""]

    # 表头：用列号 A-Z 命名（与 yuque-dl 一致，符合电子表格直觉）
    header_cells = [""]  # 第一列是行号列，表头留空
    for c in col_keys:
        # 列号转字母：0->A, 1->B, 25->Z, 26->AA
        letter = ""
        n = c
        while True:
            letter = chr(ord("A") + (n % 26)) + letter
            n = n // 26 - 1
            if n < 0:
                break
        header_cells.append(letter)
    lines.append("| " + " | ".join(header_cells) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cells)) + "|")

    # 数据行：行号最小到最大连续输出（跳过完全空的行）
    min_row, max_row = min(row_keys), max(row_keys)
    for r in range(min_row, max_row + 1):
        row_data = data.get(str(r)) or data.get(r)
        if not row_data:
            continue
        # 检查整行是否全空（跳过纯空行，减少噪音）
        cells = []
        all_empty = True
        for c in col_keys:
            cell = row_data.get(str(c)) or row_data.get(c) or {}
            v = cell.get("v") if isinstance(cell, dict) else cell
            txt = _format_cell_value(v)
            if txt:
                all_empty = False
            cells.append(txt)
        if all_empty:
            continue
        # 行首加行号
        lines.append("| " + str(r) + " | " + " | ".join(cells) + " |")

    lines.append("")
    return "\n".join(lines)


def lakesheet_to_markdown(body: str) -> str:
    """把语雀 lakesheet JSON body 还原成 markdown 表格文档。

    解码流程：
      1. JSON 解析外层 -> 取 sheet 字段（一个字符串）
      2. sheet.encode('latin1') -> zlib.decompress（magic 789c）-> 内层 JSON 字符串
      3. 内层是 sheet 列表，每个 sheet 生成一个 markdown 表格

    失败时抛异常，由调用方决定是否保留原 body。
    """
    if not body:
        raise ValueError("empty body")
    outer = json.loads(body)
    sheet_str = outer.get("sheet")
    if not sheet_str:
        raise ValueError("no sheet field in lakesheet")
    # sheet 字符串是 latin1 编码的 zlib 压缩字节（JS 端 pako 等价处理）
    raw_bytes = sheet_str.encode("latin1")
    decompressed = zlib.decompress(raw_bytes)
    inner_text = decompressed.decode("utf-8", errors="replace")
    inner = json.loads(inner_text)

    # 内层是 sheet 列表
    if isinstance(inner, list):
        sheets = inner
    elif isinstance(inner, dict):
        # 兼容单 sheet 包成对象的情况
        sheets = [inner]
    else:
        raise ValueError(f"unexpected inner type: {type(inner)}")

    parts = ["<!-- lakesheet 已解码为 markdown 表格 -->", ""]
    for s in sheets:
        if isinstance(s, dict):
            parts.append(_sheet_to_markdown(s))
            parts.append("")
    result = "\n".join(parts).rstrip() + "\n"
    return result


def try_decode_lakesheet(body: str, title: str = "") -> str:
    """若 body 是 lakesheet 则解码成 markdown，失败/非 lakesheet 则原样返回。

    用于 sync_step1 的安全调用：解码失败不丢数据，保留原 body。
    """
    if not body or not body.lstrip().startswith(_LAKESHEET_PREFIX):
        return body
    try:
        decoded = lakesheet_to_markdown(body)
        LOG.info("lakesheet 已解码为 markdown 表格: %s", title or "(未命名)")
        return decoded
    except Exception as e:
        LOG.warning("lakesheet 解码失败，保留原 body（%s）: %s", title or "(未命名)", e)
        return body


def build_session(token: str, retries: int = 3, backoff: float = 1.5) -> requests.Session:
    """构建带重试的 requests Session。"""
    s = requests.Session()
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update(
        {
            "X-Auth-Token": token,
            "User-Agent": "yuque-sync/1.0 (python-requests)",
            "Accept": "application/json",
        }
    )
    return s


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------

class Config:
    """脚本运行配置。"""

    def __init__(
        self,
        url: str,
        token: str,
        session: str,
        ctoken: str,
        output: str,
        exclude: Iterable[str],
        attachment_types: Iterable[str],
        embed_types: Iterable[str],
        limit: int = 0,
        keep_attachments: bool = False,
        clean_path: Optional[str] = None,
        no_cleanup: bool = False,
    ) -> None:
        self.url = url
        self.token = token
        self.session = session
        self.ctoken = ctoken
        self.output = Path(output).resolve()
        self.exclude = [e for e in exclude if e]
        # Step2 仅下载这些类型的附件 + 改写为本地引用
        self.attachment_types = [e.lower().lstrip(".") for e in attachment_types]
        # Step3 仅把这些类型的「本地附件引用」转 md 并原地嵌入
        self.embed_types = [e.lower().lstrip(".") for e in embed_types]
        self.limit = int(limit) if limit and int(limit) > 0 else 0
        # 是否在 embed 转换内联后保留原始附件文件（默认 False：转换内联后删除）
        self.keep_attachments = bool(keep_attachments)
        # 是否跳过本地清理（Step1.5）。默认 False=每次同步后自动清理本地多余文件
        self.no_cleanup = bool(no_cleanup)
        # 清理模式目标目录（仅 --clean-all-attachments 时非空）：此时不需要语雀凭据
        self.clean_path = Path(clean_path).expanduser().resolve() if clean_path else None
        if self.clean_path:
            # 清理模式：不需要 url/token/session/ctoken，跳过 URL 与 Cookie 解析
            return

        # 解析 URL：https://<host>/<login>/<repo>
        host, login, repo = self._parse_url(url)
        self.host = host
        self.api_base = f"https://{host}/api/v2"
        self.namespace = f"{login}/{repo}"
        self.referer = f"https://{host}/"
        # 下载附件用的 Cookie 头
        self.cookie = f"_yuque_session={session}; yuque_ctoken={ctoken}"

    @staticmethod
    def _parse_url(url: str) -> Tuple[str, str, str]:
        parts = urlsplit(url.strip())
        if not parts.netloc:
            raise ValueError(f"无效的知识库 URL: {url}")
        path = [p for p in parts.path.split("/") if p]
        if len(path) < 2:
            raise ValueError(
                f"知识库 URL 需包含 <login>/<repo> 两段路径: {url}"
            )
        return parts.netloc, path[0], path[1]

    def cookie_header(self) -> str:
        return self.cookie


def parse_args(argv: Optional[List[str]] = None) -> Config:
    p = argparse.ArgumentParser(
        prog="yuque_sync",
        description="语雀知识库增量同步工具（含附件下载与转 Markdown）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("-V", "--version", action="version",
                   version=f"yuque_sync {__version__}")
    p.add_argument("--url", default=os.environ.get("YUQUE_URL"),
                   help="语雀知识库首页地址，如 https://xxx.yuque.com/<login>/<repo>")
    p.add_argument("--token", default=os.environ.get("YUQUE_TOKEN"),
                   help="语雀 Access Token（API 读取用）")
    p.add_argument("--session", default=os.environ.get("YUQUE_SESSION"),
                   help="_yuque_session 的值（下载附件用）")
    p.add_argument("--ctoken", default=os.environ.get("YUQUE_CTOKEN"),
                   help="yuque_ctoken 的值（下载附件用）")
    p.add_argument("--output", default=os.environ.get("YUQUE_OUTPUT", DEFAULT_OUTPUT_DIR),
                   help=f"本地下载目录（默认 {DEFAULT_OUTPUT_DIR}）")
    _env_exclude = [e for e in os.environ.get("YUQUE_EXCLUDE", "").split() if e]
    p.add_argument("--exclude", nargs="*", default=_env_exclude,
                   help="排除的文档名关键字，可多个，任一命中即跳过"
                        "（也可用环境变量 YUQUE_EXCLUDE，空格分隔多个关键字）")
    p.add_argument("--attachment-types", nargs="*", default=DEFAULT_ATTACHMENT_TYPES,
                   help=f"Step2：仅下载这些类型的附件文件并改写为本地相对路径引用"
                        f"（默认 {' '.join(DEFAULT_ATTACHMENT_TYPES)}）")
    p.add_argument("--embed-types", nargs="*", default=DEFAULT_EMBED_TYPES,
                   help=f"Step3：把这些类型的附件转成 markdown 并原地嵌入到引用处、删除原引用与附件文件"
                        f"（默认 {' '.join(DEFAULT_EMBED_TYPES)}）")
    p.add_argument("--limit", type=int, default=0,
                   help="仅同步前 N 个文档（调试用，0 表示不限制）")
    p.add_argument("--keep-attachments", action="store_true",
                   help="保留附件原始文件（默认：embed 类型的附件转 md 嵌入后删除原始文件）")
    p.add_argument("--no-cleanup", action="store_true",
                   help="跳过本地清理（默认：每次同步后自动清理命中exclude的文件、"
                        "语雀侧已不存在的孤儿文档及其附件、空目录）")
    p.add_argument("--clean-all-attachments", metavar="PATH", default=None,
                   help="清理模式：递归删除 PATH 目录及其所有子目录下的附件文件（保留 .md）。"
                        "仅此参数即可，无需 --url/--token 等")
    p.add_argument("-v", "--verbose", action="store_true", help="输出调试日志")

    args = p.parse_args(argv)
    setup_logging(args.verbose)

    # 清理模式：仅需目录路径，不校验语雀凭据，直接返回
    if args.clean_all_attachments:
        return Config(
            url="", token="", session="", ctoken="",
            output=args.output,
            exclude=args.exclude,
            attachment_types=args.attachment_types,
            embed_types=args.embed_types,
            limit=args.limit,
            keep_attachments=args.keep_attachments,
            clean_path=args.clean_all_attachments,
            no_cleanup=args.no_cleanup,
        )

    missing = []
    if not args.url:
        missing.append("--url")
    if not args.token:
        missing.append("--token")
    if not args.session:
        missing.append("--session")
    if not args.ctoken:
        missing.append("--ctoken")
    if missing:
        p.error("缺少必填参数: " + ", ".join(missing) +
                "（也可用环境变量 YUQUE_URL/YUQUE_TOKEN/YUQUE_SESSION/YUQUE_CTOKEN）")

    return Config(
        url=args.url,
        token=args.token,
        session=args.session,
        ctoken=args.ctoken,
        output=args.output,
        exclude=args.exclude,
        attachment_types=args.attachment_types,
        embed_types=args.embed_types,
        limit=args.limit,
        keep_attachments=args.keep_attachments,
        no_cleanup=args.no_cleanup,
    )


# ---------------------------------------------------------------------------
# 工具预检查
# ---------------------------------------------------------------------------

def find_soffice() -> Optional[str]:
    """跨平台探测 LibreOffice 可执行文件路径（用于 .doc -> .docx）。

    Windows 下优先用 soffice.com（控制台子系统，命令行调用不弹窗、不阻塞）。
    """
    sysname = platform.system()
    candidates: List[str]
    if sysname == "Windows":
        candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.com",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.com",
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    elif sysname == "Darwin":
        candidates = ["/Applications/LibreOffice.app/Contents/MacOS/soffice"]
    else:
        candidates = ["/usr/bin/soffice", "/usr/bin/libreoffice", "/opt/libreoffice/program/soffice"]
    for c in candidates:
        if Path(c).exists():
            return c
    return shutil.which("soffice") or shutil.which("libreoffice")


def _pip_install(packages: List[str]) -> bool:
    """用当前 Python 解释器全局安装 pip 包。成功返回 True。

    使用 sys.executable 确保装到运行脚本的同一环境（避免多环境装错）。
    """
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    LOG.info("自动安装依赖: %s", " ".join(packages))
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        LOG.error("pip 调用失败: %s", e)
        return False
    if proc.returncode != 0:
        LOG.error("pip 安装失败（返回码 %d）", proc.returncode)
        # 打印 pip 的错误输出末尾便于排查
        err = (proc.stderr or proc.stdout or "").strip()
        if err:
            LOG.error("pip 输出:\n%s", err[-1500:])
        return False
    LOG.info("pip 安装完成: %s", " ".join(packages))
    return True


# 需要自动 pip 安装的 Python 包：import 名 -> 安装规格
# 注：.doc 转 .docx 依赖系统级 LibreOffice（无法 pip 安装），见 check_tools / find_soffice
_PIP_PACKAGES = {
    "markitdown": "markitdown[all]",
    "xmindparser": "xmindparser",
}


def _spec_found(name: str) -> bool:
    """安全检测模块是否可导入。find_spec 对不存在的顶层包会抛 ModuleNotFoundError。"""
    try:
        return importlib.util.find_spec(name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def check_tools() -> None:
    """启动时预检查转换依赖，缺失自动 pip 安装。

    - markitdown：docx/pdf/xls/xlsx 转 md（Step3 embed 用）
    - xmindparser：xmind 转 md（Step3 embed 用）
    - LibreOffice（系统级，无法 pip）：.doc -> .docx，缺失仅警告
    """
    missing = [name for name in _PIP_PACKAGES if not _spec_found(name)]
    if missing:
        specs = [_PIP_PACKAGES[n] for n in missing]
        LOG.info("检测到缺失依赖，开始自动安装: %s", " ".join(specs))
        if not _pip_install(specs):
            LOG.error("依赖自动安装失败，请手动执行: pip install %s", " ".join(specs))
            sys.exit(1)
        for name in missing:
            sys.modules.pop(name, None)
        still_missing = [name for name in missing if not _spec_found(name)]
        if still_missing:
            LOG.error("安装后仍无法导入: %s。请手动检查 Python 环境。", still_missing)
            sys.exit(1)
        LOG.info("依赖自动安装成功: %s", ", ".join(missing))

    soffice = find_soffice()
    if soffice:
        try:
            flags = {}
            if platform.system() == "Windows":
                flags["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.run([soffice, "--version"], capture_output=True, check=False,
                           timeout=20, stdin=subprocess.DEVNULL, **flags)
            LOG.info("工具预检查通过：markitdown / xmindparser / LibreOffice(%s)", soffice)
        except Exception as e:  # pragma: no cover
            LOG.warning("LibreOffice 探测到 %s 但运行失败: %s。.doc 附件将被跳过。", soffice, e)
    else:
        LOG.warning("未找到 LibreOffice（soffice）。.doc 附件将无法转换；其他类型不受影响。"
                    "如需处理 .doc，请从 https://www.libreoffice.org/download/ 安装。")


# ---------------------------------------------------------------------------
# 语雀 API 客户端
# ---------------------------------------------------------------------------

class YuqueClient:
    """封装语雀 API 读取与附件下载。"""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.session = build_session(cfg.token)

    # ---- API 读取（用 X-Auth-Token）----

    def _api_get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.cfg.api_base}{path}"
        for attempt in range(4):
            try:
                resp = self.session.get(url, params=params, timeout=HTTP_TIMEOUT)
            except requests.RequestException as e:
                LOG.warning("网络异常 %s: %s（第 %d 次重试）", path, e, attempt + 1)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code == 429:
                wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                LOG.warning("触发限流（429），等待 %.1fs 后重试", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("code") and data["code"] != 0 and data["code"] != 200:
                raise RuntimeError(f"语雀 API 返回错误: {data.get('code')} {data.get('message')}")
            return data
        raise RuntimeError(f"请求多次失败: {url}")

    def get_repo(self) -> Dict[str, Any]:
        """获取知识库信息（含 toc_yml）。"""
        data = self._api_get(f"/repos/{self.cfg.namespace}")
        return data.get("data", {})

    def get_doc(self, slug: str) -> Dict[str, Any]:
        """获取单个文档详情（body 即 markdown）。"""
        data = self._api_get(f"/repos/{self.cfg.namespace}/docs/{slug}")
        return data.get("data", {})

    # ---- 附件下载（用 session + ctoken Cookie + Referer，自动跟随重定向）----

    def download_attachment(self, url: str, dest: Path) -> None:
        """下载附件到 dest。语雀会 302 跳转到预签名 OSS URL，requests 自动跟随。"""
        headers = {
            "Cookie": self.cfg.cookie_header(),
            "Referer": self.cfg.referer,
            "User-Agent": "Mozilla/5.0 (yuque-sync)",
        }
        # 用独立 session 避免把 X-Auth-Token 带去 OSS
        for attempt in range(4):
            try:
                with requests.get(
                    url, headers=headers, stream=True,
                    allow_redirects=True, timeout=HTTP_TIMEOUT,
                ) as resp:
                    if resp.status_code == 429:
                        wait = float(resp.headers.get("Retry-After", 2 ** attempt))
                        LOG.warning("附件下载触发限流（429），等待 %.1fs", wait)
                        time.sleep(wait)
                        continue
                    if resp.status_code == 401 or resp.status_code == 302:
                        # 极少数情况下未跟随重定向
                        loc = resp.headers.get("Location", "")
                        raise RuntimeError(f"附件下载认证失败(状态 {resp.status_code})，跳转: {loc}")
                    resp.raise_for_status()
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with open(dest, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)
                    return
            except requests.RequestException as e:
                LOG.warning("附件下载异常 %s: %s（第 %d 次重试）", dest.name, e, attempt + 1)
                time.sleep(2 ** attempt)
        raise RuntimeError(f"附件下载多次失败: {url}")


# ---------------------------------------------------------------------------
# TOC 解析与目录树重建
# ---------------------------------------------------------------------------

class TocNode:
    __slots__ = (
        "type", "title", "uuid", "parent_uuid", "level", "url", "doc_id",
    )

    def __init__(self, raw: Dict[str, Any]) -> None:
        self.type = str(raw.get("type", "")).upper()
        self.title = str(raw.get("title", "")).strip()
        self.uuid = str(raw.get("uuid", "")).strip()
        self.parent_uuid = str(raw.get("parent_uuid", "")).strip()
        self.level = int(raw.get("level", 0) or 0)
        self.url = str(raw.get("url", "")).strip()  # DOC 节点的 slug
        self.doc_id = raw.get("doc_id", "")

    @property
    def is_doc(self) -> bool:
        return self.type == "DOC" and bool(self.url)

    @property
    def is_dir(self) -> bool:
        return self.type == "TITLE"


def parse_toc(toc_yml: str) -> List[TocNode]:
    """解析 toc_yml，返回节点列表（过滤掉 META）。"""
    if not toc_yml:
        return []
    try:
        data = yaml.safe_load(toc_yml)
    except yaml.YAMLError as e:
        LOG.error("toc_yml 解析失败: %s", e)
        return []
    if not isinstance(data, list):
        return []
    nodes: List[TocNode] = []
    for raw in data:
        if not isinstance(raw, dict):
            continue
        node = TocNode(raw)
        if node.type == "META":
            continue
        nodes.append(node)
    return nodes


def build_tree(nodes: List[TocNode]) -> Dict[str, TocNode]:
    """uuid -> node 映射。"""
    return {n.uuid: n for n in nodes if n.uuid}


def compute_local_path(node: TocNode, tree: Dict[str, TocNode]) -> Tuple[str, str]:
    """计算节点的本地相对路径：(dir_relpath, full_relpath)。

    沿 parent_uuid 向上回溯，TITLE 作为目录段，DOC 作为文件名（不含扩展名）。
    """
    dir_parts: List[str] = []
    cur: Optional[TocNode] = node
    # 先收集祖先 TITLE 目录
    parent = tree.get(node.parent_uuid) if node.parent_uuid else None
    while parent:
        if parent.is_dir and parent.title:
            dir_parts.append(sanitize_name(parent.title))
        elif parent.is_doc:
            # 父节点是 DOC（语雀允许文档嵌文档），把父文档名也作为一层目录
            dir_parts.append(sanitize_name(parent.title))
        parent = tree.get(parent.parent_uuid) if parent.parent_uuid else None
    dir_parts.reverse()
    dir_rel = os.path.join(*dir_parts) if dir_parts else ""

    name = sanitize_name(node.title) if node.title else node.url
    full_rel = os.path.join(dir_rel, f"{name}.md") if dir_rel else f"{name}.md"
    return dir_rel, full_rel


# ---------------------------------------------------------------------------
# Step 1：文档增量同步
# ---------------------------------------------------------------------------

def collect_ancestor_titles(node: TocNode, tree: Dict[str, TocNode]) -> List[str]:
    """收集节点的所有祖先（TITLE/DOC）标题，从根到父级，不含节点自身。"""
    titles: List[str] = []
    parent = tree.get(node.parent_uuid) if node.parent_uuid else None
    while parent:
        if parent.title:
            titles.append(parent.title)
        parent = tree.get(parent.parent_uuid) if parent.parent_uuid else None
    titles.reverse()
    return titles


def doc_is_excluded(title: str, exclude: List[str]) -> bool:
    """单个字符串是否命中任一排除关键字。"""
    if not exclude:
        return False
    return any(kw in title for kw in exclude)


def node_is_excluded(node: TocNode, tree: Dict[str, TocNode], exclude: List[str]) -> bool:
    """文档节点是否应被排除：文档自身标题或任一祖先目录名命中关键字。

    （注：此规则只作用于「是否下载该 md 文档」，不影响文档内附件的下载）
    """
    if not exclude:
        return False
    if doc_is_excluded(node.title or node.url, exclude):
        return True
    for ancestor_title in collect_ancestor_titles(node, tree):
        if doc_is_excluded(ancestor_title, exclude):
            return True
    return False


def scan_local_docs(root: Path) -> Dict[str, int]:
    """扫描本地已存在文档，返回 {相对路径(去时间戳) -> timestamp}。

    key 用「相对 root 的目录路径 + 文件名（去掉时间戳）」，确保不同目录下的
    同名文档（语雀模板文档极常见，如「提测信息」「测试分析」）不会互相覆盖。

    例如 root/需求A/测试分析-1782121686.md -> key = '需求A/测试分析'
         root/测试分析-1782121686.md        -> key = '测试分析'（根目录无前缀）
    """
    result: Dict[str, int] = {}
    if not root.exists():
        return result
    for md_path in root.rglob("*.md"):
        m = DOC_TS_RE.match(md_path.name)
        if not m:
            continue
        try:
            rel_dir = md_path.parent.relative_to(root)
        except ValueError:
            rel_dir = Path()
        name_base = m.group("title")
        # rel_dir 为空或 '.' 表示文档在 root 根目录下，key 不加目录前缀
        rel_dir_str = rel_dir.as_posix()
        if rel_dir_str and rel_dir_str != ".":
            key = f"{rel_dir_str}/{name_base}"
        else:
            key = name_base
        result[key] = int(m.group("ts"))
    return result


def cleanup_old_versions(dir_path: Path, title: str, keep_ts: int) -> None:
    """删除目录下该 title 的旧版本文件（时间戳 != keep_ts）。

    直接遍历目录、用文件名正则匹配，避免 Path.glob 对含特殊字符
    （如标题里的 / \\ ）的 pattern 在 Python 3.12 上报错。
    """
    if not dir_path.is_dir():
        return
    title_escaped = re.escape(title)
    old_re = re.compile(rf"^{title_escaped}-(?P<ts>\d{{10}})\.md$")
    for f in dir_path.iterdir():
        if not f.is_file():
            continue
        m = old_re.match(f.name)
        if m and int(m.group("ts")) != keep_ts:
            try:
                f.unlink()
                LOG.info("清理旧版本: %s", f)
            except OSError as e:
                LOG.warning("清理旧版本失败 %s: %s", f, e)


def sync_step1(client: YuqueClient, cfg: Config) -> Tuple[List[Path], List[Path], Set[str], Path]:
    """Step1：同步文档。

    返回 (changed_files, all_processed_files, kept_keys, root)：
      - changed_files：本次「新增或更新」的 md（Step2 需要处理这些的附件）
      - all_processed_files：本次实际处理过的所有 md（含跳过/已最新），供日志/调试
      - kept_keys：语雀侧合法（未被 exclude）文档的本地索引 key 集合，供 Step1.5 清理比对
      - root：本地实际输出根目录（cfg.output / 知识库名），供 Step1.5 清理
    """
    LOG.info("=== Step1：同步文档 ===")
    LOG.info("获取知识库信息: %s", cfg.namespace)
    repo = client.get_repo()
    repo_name = repo.get("name", "yuque_repo")
    toc_yml = repo.get("toc_yml", "")
    LOG.info("知识库名称: %s", repo_name)

    nodes = parse_toc(toc_yml)
    tree = build_tree(nodes)
    doc_nodes = [n for n in nodes if n.is_doc]
    total = len(doc_nodes)
    LOG.info("TOC 解析完成：文档 %d 个（已过滤 TITLE/META 节点）", total)

    root = cfg.output / sanitize_name(repo_name)
    root.mkdir(parents=True, exist_ok=True)
    local_index = scan_local_docs(root)

    changed: List[Path] = []      # 新增/更新的（Step2 要处理）
    all_processed: List[Path] = []  # 所有处理过的（含跳过）
    kept_keys: Set[str] = set()    # 语雀侧合法文档的本地索引 key（供 Step1.5 清理比对）
    skipped = 0
    excluded = 0
    processed = 0  # 实际处理（含下载/跳过/已最新）的计数，排除的不算

    for i, node in enumerate(doc_nodes, 1):
        title = node.title or node.url
        # 排除关键字：文档名或任一祖先目录名命中即跳过（不影响附件）
        if node_is_excluded(node, tree, cfg.exclude):
            excluded += 1
            continue

        # limit 限制（按实际处理数算，到达即停）
        if cfg.limit and processed >= cfg.limit:
            LOG.info("已达 --limit %d，停止同步（剩余 %d 文档未处理）",
                     cfg.limit, total - i + 1)
            break
        processed += 1

        try:
            doc = client.get_doc(node.url)
        except Exception as e:
            LOG.error("[%d/%d] 下载失败: %s - %s", i, total, title, e)
            continue

        body = doc.get("body") or ""
        # 语雀表格（sheet）文档的 body 是 lakesheet 私有格式，解码成 markdown 表格
        body = try_decode_lakesheet(body, title)
        ts = iso_to_timestamp(doc.get("content_updated_at") or doc.get("updated_at") or "")
        name_base = sanitize_name(title)

        dir_rel, full_rel = compute_local_path(node, tree)
        target_dir = (root / dir_rel) if dir_rel else root
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / f"{name_base}-{ts}.md"

        # 用相对路径作 key 查询本地索引，避免不同目录同名文档互相覆盖
        rel_dir_str = Path(dir_rel).as_posix() if dir_rel else ""
        index_key = f"{rel_dir_str}/{name_base}" if rel_dir_str and rel_dir_str != "." else name_base
        # 记录为语雀侧合法文档（无论后续跳过/新增/写入失败，都不应被 Step1.5 当孤儿删除）
        kept_keys.add(index_key)
        old_ts = local_index.get(index_key)
        if old_ts == ts and target_path.exists():
            skipped += 1
            # 跳过日志始终输出，便于确认进度（无变化属正常）
            LOG.info("[%d/%d] 跳过(已最新): %s", i, total, title)
            all_processed.append(target_path)
            continue

        # 写入文件
        try:
            target_path.write_text(body, encoding="utf-8")
            # 清理旧版本
            cleanup_old_versions(target_dir, name_base, ts)
            if old_ts is None:
                LOG.info("[%d/%d] 新增: %s", i, total, title)
            else:
                LOG.info("[%d/%d] 更新: %s (%d -> %d)", i, total, title, old_ts, ts)
            changed.append(target_path)
            all_processed.append(target_path)
        except OSError as e:
            LOG.error("[%d/%d] 写入失败: %s - %s", i, total, title, e)

    new_or_updated = len(changed)
    limit_note = f"，限制前 {cfg.limit}" if cfg.limit else ""
    LOG.info(
        "Step1 完成: 共 %d 文档%s，新增/更新 %d，跳过(已最新) %d，排除 %d",
        total, limit_note, new_or_updated, skipped, excluded,
    )
    return changed, all_processed, kept_keys, root


# ---------------------------------------------------------------------------
# Step 1.5：本地清理（删除命中 exclude 的文件、语雀侧已不存在的孤儿文档及附件、空目录）
# ---------------------------------------------------------------------------

# 受保护的特殊文件名（清理时跳过，不删除）
_PROTECTED_NAMES = {MANIFEST_FILENAME}


def _path_hits_exclude(rel_posix: str, exclude: List[str]) -> bool:
    """判断文件的相对路径（posix）是否命中任一 exclude 关键字。

    对整条路径做子串匹配，覆盖目录名和文件名两种情况。
    """
    if not exclude:
        return False
    return any(kw in rel_posix for kw in exclude)


def cleanup_local(root: Path, kept_keys: Set[str], exclude: List[str]) -> Dict[str, int]:
    """Step1.5：清理本地多余文件。

    清理四类对象：
      1. 命中 exclude 关键字的 .md 文档（文件名或所在目录路径含关键字）
      2. 语雀侧已不存在的孤儿 .md 文档（本地有、但 kept_keys 中没有）
      3. 上述被删文档同目录下的孤儿附件（非 .md 文件，其目录已无 .md 文档）
      4. 清理后产生的空目录

    参数:
      - root：本地输出根目录（与 sync_step1 一致，cfg.output / 知识库名）
      - kept_keys：语雀侧合法文档的本地索引 key 集合（由 sync_step1 收集）
      - exclude：排除关键字列表

    返回各分类删除计数。
    """
    stats = {"excluded_md": 0, "orphan_md": 0, "orphan_attach": 0, "empty_dirs": 0, "failed": 0}
    if not root.exists():
        return stats

    LOG.info("=== Step1.5：本地清理 ===")

    # ---- 1 & 2. 扫描 .md 文档：删命中 exclude 的 + 孤儿 ----
    for md_path in root.rglob("*.md"):
        name = md_path.name
        if name in _PROTECTED_NAMES:
            continue
        try:
            rel = md_path.relative_to(root)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        m = DOC_TS_RE.match(name)
        if not m:
            continue
        name_base = m.group("title")
        # 构建与 scan_local_docs / kept_keys 一致的 index_key
        rel_dir = rel.parent.as_posix()
        if rel_dir and rel_dir != ".":
            local_key = f"{rel_dir}/{name_base}"
        else:
            local_key = name_base

        should_delete = False
        reason = ""
        if _path_hits_exclude(rel_posix, exclude):
            should_delete = True
            reason = "命中exclude"
            stats["excluded_md"] += 1
        elif local_key not in kept_keys:
            should_delete = True
            reason = "孤儿(语雀侧已不存在)"
            stats["orphan_md"] += 1

        if should_delete:
            try:
                md_path.unlink()
                LOG.info("  删除文档(%s): %s", reason, rel_posix)
            except OSError as e:
                LOG.warning("  删除文档失败 %s: %s", rel_posix, e)
                stats["failed"] += 1

    # ---- 3. 扫描非 .md 附件：删命中 exclude 的 + 孤儿附件（目录下已无 .md）----
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        name = p.name
        if name in _PROTECTED_NAMES:
            continue
        if name.lower().endswith(".md"):
            continue
        try:
            rel = p.relative_to(root)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        # 命中 exclude 的附件直接删
        if _path_hits_exclude(rel_posix, exclude):
            try:
                p.unlink()
                stats["orphan_attach"] += 1
                LOG.info("  删除附件(命中exclude): %s", rel_posix)
            except OSError as e:
                LOG.warning("  删除附件失败 %s: %s", rel_posix, e)
                stats["failed"] += 1
            continue
        # 孤儿附件：所在目录（含子目录）已无任何 .md 文档
        parent = p.parent
        has_md = any(parent.rglob("*.md"))
        if not has_md:
            try:
                p.unlink()
                stats["orphan_attach"] += 1
                LOG.info("  删除孤儿附件(目录无文档): %s", rel_posix)
            except OSError as e:
                LOG.warning("  删除孤儿附件失败 %s: %s", rel_posix, e)
                stats["failed"] += 1

    # ---- 4. 清理空目录（自底向上）----
    all_dirs = [d for d in root.rglob("*") if d.is_dir()]
    # 按路径深度降序，先处理最深层目录
    all_dirs.sort(key=lambda d: len(d.parts), reverse=True)
    for d in all_dirs:
        try:
            if not any(d.iterdir()):
                d.rmdir()
                stats["empty_dirs"] += 1
                LOG.info("  删除空目录: %s", d.relative_to(root).as_posix())
        except OSError:
            # 目录非空或无权限，忽略
            pass

    LOG.info(
        "Step1.5 完成: 删除命中exclude文档 %d，孤儿文档 %d，孤儿附件 %d，空目录 %d，失败 %d",
        stats["excluded_md"], stats["orphan_md"], stats["orphan_attach"],
        stats["empty_dirs"], stats["failed"],
    )
    return stats


# ---------------------------------------------------------------------------
# Step 2：附件下载与转换
# ---------------------------------------------------------------------------

class Manifest:
    """附件增量记录，存于 output 根目录。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: Dict[str, Dict[str, Any]] = {}
        if path.exists():
            try:
                self.data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {}

    def get(self, url: str) -> Optional[Dict[str, Any]]:
        return self.data.get(url)

    def set(self, url: str, upload_ts: str, local_path: str) -> None:
        self.data[url] = {"upload_ts": upload_ts, "local_path": local_path}

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except OSError as e:
            LOG.warning("manifest 写入失败: %s", e)


def _ext_of(name: str) -> str:
    """取文件名扩展名（小写、不含点）；无扩展名或不像扩展名则返回空串。

    扩展名需为纯字母数字且长度 <= 8，避免把 URL 中的 '.com/...' 误判为扩展名。
    """
    dot = name.rfind(".")
    if dot < 0:
        return ""
    ext = name[dot + 1:].lower()
    # 合法扩展名只含字母数字，且不含路径/URL 分隔符
    if not ext.isalnum() or len(ext) > 8:
        return ""
    return ext


def _url_path_ext(url: str) -> str:
    """从 URL 的路径部分取末尾扩展名（去掉 query/fragment 后），小写不含点。

    用于判断该 URL 是否指向一个真实文件。例如：
      .../1782109285319-yuque.docx  -> 'docx'
      .../docs/share/1e8a2436-...?# -> ''（无扩展名，是网页/文档链接）
      .../doc.html?x=1             -> 'html'
    """
    path = urlsplit(url).path
    base = path.rsplit("/", 1)[-1]
    dot = base.rfind(".")
    return base[dot + 1:].lower() if dot >= 0 else ""


def _attach_local_name(attach_name: str, url: str, doc_ts: str) -> str:
    """推导附件下载到文档旁的文件名。

    规则：
      - 优先用链接文本 name；若 name 含 URL/路径字符（不像干净文件名），则用 URL 路径末段；
      - 在 stem 后追加文档的时间戳后缀（与所属文档一致），便于增量管理与清理旧版本；
      - 清洗非法字符。
    例：name='MOPRO-1852.xmind', doc_ts='1782121686' -> 'MOPRO-1852-1782121686.xmind'
    """
    candidate = attach_name.strip()
    if not candidate or re.search(r"[/?#]|https?://", candidate):
        base = urlsplit(url).path.rsplit("/", 1)[-1]
        if base:
            candidate = base
    p = Path(candidate)
    stem, suffix = p.stem, p.suffix
    if doc_ts:
        stem = f"{stem}-{doc_ts}"
    return sanitize_name(stem + (suffix if suffix else ""))


def extract_attachments(body: str, types: List[str]) -> List[Tuple[str, str]]:
    """Step2：从 markdown 提取远程附件 (name, url)，仅限 types 指定扩展名。

    - 匹配 [name](http(s)://...) 形式的链接；
    - 链接文本(name) 或 URL 路径末尾扩展名命中 types 才提取；
    - 图片/网页/文档分享链接不提取（保持原样）。
    """
    want = {e.lower().lstrip(".") for e in types}
    result: List[Tuple[str, str]] = []
    seen = set()
    for m in REMOTE_LINK_RE.finditer(body):
        name = m.group("name").strip()
        url = m.group("url").strip()
        if not name or not url:
            continue
        ext = _ext_of(name) or _url_path_ext(url)
        if ext not in want:
            continue
        key = (name, url)
        if key in seen:
            continue
        seen.add(key)
        result.append((name, url))
    return result


def extract_local_embed_links(body: str, types: List[str]) -> List[Tuple[str, str]]:
    """Step3：从 markdown 提取「本地附件引用」(name, local_ref)，仅限 types 指定扩展名。

    - 匹配 [name](本地路径)，本地路径不以 http(s):// 开头；
    - 扩展名命中 types 才提取；
    - 排除图片，排除已被嵌入块包裹的引用（避免重复嵌入）。
    """
    want = {e.lower().lstrip(".") for e in types}
    result: List[Tuple[str, str]] = []
    seen = set()
    for m in LOCAL_LINK_RE.finditer(body):
        name = m.group("name").strip()
        local_ref = m.group("url").strip()
        if not name or not local_ref:
            continue
        ext = _ext_of(name) or _ext_of(local_ref)
        if ext not in want or ext in IMAGE_EXTS:
            continue
        key = (name, local_ref)
        if key in seen:
            continue
        seen.add(key)
        result.append((name, local_ref))
    return result


def rewrite_link_url(body: str, url: str, local_ref: str) -> str:
    """把文档中所有指向 url 的 markdown 链接目标改写为 local_ref（本地相对路径）。"""
    return body.replace("](" + url + ")", "](" + local_ref + ")")


def parse_attach_url_ts(url: str) -> str:
    """从附件 URL 解析上传时间戳（毫秒字符串），找不到返回空。"""
    m = ATTACH_URL_TS_RE.search(url)
    return m.group(1) if m else ""


def find_inline_block(lines: List[str], attach_name: str) -> Optional[Tuple[int, int]]:
    """查找已存在的附件插入块 [begin_line_idx, end_line_idx]（闭区间）。"""
    begin_marker = ATTACH_BLOCK_BEGIN.format(name=attach_name)
    begin_idx = None
    for i, ln in enumerate(lines):
        if begin_marker in ln:
            begin_idx = i
            break
    if begin_idx is None:
        return None
    for j in range(begin_idx + 1, len(lines)):
        if ATTACH_BLOCK_END in lines[j]:
            return (begin_idx, j)
    return (begin_idx, begin_idx)


def find_attach_link_line(lines: List[str], attach_name: str, url: str) -> Optional[int]:
    """查找附件 markdown 链接所在行索引。"""
    # 用文件名匹配（最稳）；同时兼顾 URL 可能被截断
    name_escaped = re.escape(attach_name)
    link_re = re.compile(rf"\[{name_escaped}\]\(", re.IGNORECASE)
    for i, ln in enumerate(lines):
        if link_re.search(ln) and url in ln:
            return i
        if link_re.search(ln):
            return i
        # 兜底：行内同时包含名和 url
        if attach_name in ln and url in ln:
            return i
    return None


def replace_inline_block(lines: List[str], attach_name: str, new_md: str) -> List[str]:
    """用 new_md 替换/插入附件内联块。

    策略：找到链接行 -> 检查是否已有内联块 -> 有则替换，无则在链接行下一行插入。
    """
    begin_marker = ATTACH_BLOCK_BEGIN.format(name=attach_name)
    link_idx = find_attach_link_line(lines, attach_name, "")  # name-only 匹配
    existing = find_inline_block(lines, attach_name)

    block = [begin_marker, "", new_md.strip(), "", ATTACH_BLOCK_END]

    if existing:
        b, e = existing
        # 替换 [b, e] 为新块
        return lines[:b] + block + lines[e + 1:]

    if link_idx is not None:
        return lines[: link_idx + 1] + [""] + block + lines[link_idx + 1:]

    # 找不到链接行，追加到末尾
    LOG.warning("未找到附件链接行，追加到文档末尾: %s", attach_name)
    return lines + ["", begin_marker, "", new_md.strip(), "", ATTACH_BLOCK_END]


def replace_link_with_embed(lines: List[str], attach_name: str, ref: str, new_md: str) -> List[str]:
    """Step3：用嵌入块替换整个附件链接 [name](ref)。

    - 先查已有的同名嵌入块，有则替换其内容；
    - 否则定位链接行（同时匹配 name 和 ref），用嵌入块替换该行；
    - 嵌入块 = begin_marker + 转换的 md + end_marker（原链接被删除，内容原地嵌入）。
    """
    begin_marker = ATTACH_BLOCK_BEGIN.format(name=attach_name)
    block = [begin_marker, "", new_md.strip(), "", ATTACH_BLOCK_END]
    existing = find_inline_block(lines, attach_name)
    if existing:
        b, e = existing
        return lines[:b] + block + lines[e + 1:]
    # 精确匹配 name + ref
    name_escaped = re.escape(attach_name)
    ref_escaped = re.escape(ref)
    link_re = re.compile(rf"\[{name_escaped}\]\({ref_escaped}\)", re.IGNORECASE)
    for i, ln in enumerate(lines):
        if link_re.search(ln):
            # 整行只有链接时直接替换整行；否则只替换链接片段
            stripped = ln.strip()
            if link_re.fullmatch(stripped):
                return lines[:i] + block + lines[i + 1:]
            new_ln = link_re.sub("\n".join(block), ln)
            return lines[:i] + [new_ln] + lines[i + 1:]
    LOG.warning("未找到附件链接 [name](ref)，追加到文档末尾: %s (%s)", attach_name, ref)
    return lines + [""] + block


# ---- 文档转换器（Step3 embed 用）----

def _soffice_convert_to_docx(doc_path: Path, outdir: Path) -> Path:
    """用 LibreOffice 把 .doc 转 .docx，返回 docx 路径。"""
    soffice = find_soffice()
    if not soffice:
        raise RuntimeError("LibreOffice 未安装，无法转换 .doc 附件。")
    outdir.mkdir(parents=True, exist_ok=True)
    cmd = [soffice, "--headless", "--convert-to", "docx",
           "--outdir", str(outdir.resolve()), str(doc_path.resolve())]
    flags: Dict[str, Any] = {}
    if platform.system() == "Windows":
        flags["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    LOG.info("LibreOffice 转换: %s", doc_path.name)
    proc = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, **flags)
    if proc.returncode != 0:
        raise RuntimeError(
            f"LibreOffice 转换失败: {proc.stderr.decode('utf-8', 'ignore') or proc.stdout.decode('utf-8', 'ignore')}"
        )
    docx_path = outdir / (doc_path.stem + ".docx")
    if not docx_path.exists():
        raise RuntimeError(f"LibreOffice 转换后未找到输出文件: {docx_path}")
    return docx_path


def convert_to_markdown(path: Path) -> str:
    """根据扩展名把附件转为 markdown 字符串（Step3 embed 用）。

    - xmind -> xmindparser 自拼 markdown
    - doc  -> LibreOffice 转 docx 后再 markitdown
    - docx/pdf/xls/xlsx/ppt/pptx -> markitdown
    """
    ext = path.suffix.lower().lstrip(".")
    if ext == "xmind":
        return _xmind_to_md(path)
    if ext == "doc":
        tmp_dir = path.parent / ".convert_tmp"
        docx = _soffice_convert_to_docx(path, tmp_dir)
        try:
            return _markitdown_convert(docx)
        finally:
            try:
                docx.unlink()
            except OSError:
                pass
            try:
                tmp_dir.rmdir()
            except OSError:
                pass
    if ext in ("docx", "pdf", "xls", "xlsx", "ppt", "pptx"):
        return _markitdown_convert(path)
    raise ValueError(f"不支持的 embed 类型: {ext}")


def _markitdown_convert(path: Path) -> str:
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(str(path))
    text = getattr(result, "text_content", None) or str(result)
    return text.strip()


def _xmind_to_md(path: Path) -> str:
    """xmind 转 markdown，对 GBrain 知识库友好。

    格式约定：
      - 中心主题（sheet 标题）用 `#`
      - 根 topic 用 `##`
      - 其余层级用缩进的 `-` 无序列表（每层 2 空格缩进），清晰表达树状层级关系
      - 保留 notes（`>` 引用块）、labels（行尾加粗 `[标签1] [标签2]`）、makers（图标标记 `[icon:xxx]`）

    这样 GBrain 等基于 markdown 的知识库能正确读取层级与关系。
    """
    import xmindparser

    sheets = xmindparser.xmind_to_dict(str(path))
    if not sheets:
        return "_(xmind 文件为空或解析失败)_"

    lines: List[str] = []

    def emit_node(node: Any, depth: int) -> None:
        """depth: 0=根topic(##), >=1=子节点(缩进列表)。

        子节点缩进 = 2 * depth 个空格，每层一致。
        """
        if not isinstance(node, dict):
            return
        title = str(node.get("title", "")).strip()
        if not title:
            title = "（无标题）"

        # 收集附加信息：labels / makers / link
        extras: List[str] = []
        labels = node.get("labels") or []
        if labels:
            extras.append("**" + "** **".join(str(l) for l in labels) + "**")
        makers = node.get("makers") or []
        for m in makers:
            extras.append(f"`icon:{m}`")
        link = node.get("link") or ""
        if link:
            extras.append(f"[🔗]({link})")

        if depth == 0:
            # 根 topic 用二级标题
            head = f"## {title}"
            if extras:
                head += "　" + " ".join(extras)
            lines.append(head)
        else:
            indent = "  " * depth
            item = f"{indent}- {title}"
            if extras:
                item += "　" + " ".join(extras)
            lines.append(item)

        # notes 作为引用块紧跟在节点后（子节点之前），保持归属清晰
        note = (node.get("note") or "").strip()
        if note:
            indent = "  " * (depth + 1) if depth > 0 else ""
            quote_prefix = f"{indent}> " if depth > 0 else "> "
            note_lines = note.splitlines() or [""]
            for nl in note_lines:
                lines.append(f"{quote_prefix}{nl}".rstrip())

        # 递归子节点（兼容 zen 的 topics 与旧版 children.attached）
        children = node.get("topics")
        if children is None and isinstance(node.get("children"), dict):
            children = node["children"].get("attached", [])
        if isinstance(children, list):
            for c in children:
                emit_node(c, depth + 1)

    for sheet in sheets:
        if isinstance(sheet, dict):
            # sheet 标题（中心主题）用一级标题
            sheet_title = str(sheet.get("title", "")).strip() or "未命名画布"
            lines.append(f"# {sheet_title}")
            lines.append("")
            topic = sheet.get("topic")
            if topic:
                emit_node(topic, 0)
            lines.append("")  # 多画布之间空行分隔
        else:
            lines.append("# 未命名画布")
            lines.append("")

    return "\n".join(lines).strip()


def _doc_ts_from_path(md_path: Path) -> str:
    """从 Step1 文档文件名提取 10 位秒级时间戳（<title>-<ts>.md）。"""
    m = DOC_TS_RE.match(md_path.name)
    return m.group("ts") if m else ""


def sync_step2(client: YuqueClient, cfg: Config, md_files: List[Path]) -> None:
    """Step2：下载 --attachment-types 指定类型的附件到文档旁，并把引用改写为本地相对路径。

    - 仅下载、不转换、不嵌入；
    - 附件文件名带文档的时间戳后缀（如 doc_ts），便于增量管理与清理旧版本；
    - 图片/网页/非指定类型链接保持原样。
    """
    LOG.info("=== Step2：附件下载与引用本地化 ===")
    manifest_path = cfg.output / MANIFEST_FILENAME
    manifest = Manifest(manifest_path)

    attach_count = 0
    downloaded = 0
    skipped = 0
    failed = 0

    for md_path in md_files:
        try:
            body = md_path.read_text(encoding="utf-8")
        except OSError as e:
            LOG.warning("读取失败 %s: %s", md_path, e)
            continue

        attachments = extract_attachments(body, cfg.attachment_types)
        if not attachments:
            continue

        try:
            rel_display = md_path.resolve().relative_to(cfg.output)
        except ValueError:
            rel_display = md_path
        LOG.info("处理文档: %s（%d 个附件）", rel_display, len(attachments))
        changed = False
        doc_ts = _doc_ts_from_path(md_path)

        for name, url in attachments:
            attach_count += 1
            local_name = _attach_local_name(name, url, doc_ts)
            upload_ts = parse_attach_url_ts(url)
            record = manifest.get(url)
            local_path = md_path.parent / local_name

            need_download = True
            if record and record.get("upload_ts") == upload_ts and upload_ts:
                rec_path = Path(record.get("local_path", ""))
                if rec_path.exists():
                    local_path = rec_path
                    need_download = False
            elif record:
                local_path = Path(record.get("local_path", local_path))

            if need_download:
                try:
                    LOG.info("  下载附件: %s", local_name)
                    client.download_attachment(url, local_path)
                    manifest.set(url, upload_ts, str(local_path))
                    changed = True
                    downloaded += 1
                except Exception as e:
                    LOG.error("  附件下载失败 %s: %s", local_name, e)
                    failed += 1
                    continue
            else:
                skipped += 1

            # 把远程引用改写为本地相对路径
            try:
                rel = os.path.relpath(local_path, md_path.parent)
            except ValueError:
                rel = local_name
            new_body = rewrite_link_url(body, url, rel)
            if new_body != body:
                body = new_body
                changed = True

        if changed:
            try:
                md_path.write_text(body, encoding="utf-8")
            except OSError as e:
                LOG.warning("写回文档失败 %s: %s", md_path, e)

    manifest.save()
    LOG.info("Step2 完成: 遇到附件 %d，下载 %d，跳过(已最新) %d，失败 %d",
             attach_count, downloaded, skipped, failed)


def sync_step3(cfg: Config, md_files: List[Path]) -> None:
    """Step3（embed）：把 --embed-types 类型的本地附件引用转成 md，原地嵌入并删除原引用与附件文件。

    对每个 md 文档：
      - 提取本地附件引用（Step2 已本地化的引用），扩展名命中 embed_types；
      - 读取附件文件 -> 转 md -> 用嵌入块替换整个链接 -> 写回文档；
      - 写回成功后删除附件原始文件（除非 --keep-attachments）。
    """
    LOG.info("=== Step3：附件转 Markdown 嵌入 ===")
    embed_count = 0
    embedded = 0
    failed = 0

    for md_path in md_files:
        try:
            body = md_path.read_text(encoding="utf-8")
        except OSError as e:
            LOG.warning("读取失败 %s: %s", md_path, e)
            continue

        links = extract_local_embed_links(body, cfg.embed_types)
        if not links:
            continue

        try:
            rel_display = md_path.resolve().relative_to(cfg.output)
        except ValueError:
            rel_display = md_path
        LOG.info("处理文档: %s（%d 个待嵌入附件）", rel_display, len(links))
        changed = False
        converted_binaries: List[Path] = []

        for name, ref in links:
            embed_count += 1
            local_path = (md_path.parent / ref).resolve() if not Path(ref).is_absolute() else Path(ref)
            if not local_path.exists():
                LOG.warning("  附件文件不存在，跳过: %s (%s)", name, ref)
                failed += 1
                continue
            try:
                md_text = convert_to_markdown(local_path)
                lines = body.splitlines()
                new_lines = replace_link_with_embed(lines, name, ref, md_text)
                new_body = "\n".join(new_lines)
                if new_body != body:
                    body = new_body
                    changed = True
                embedded += 1
                LOG.info("  嵌入成功: %s -> md(%d 字符)", name, len(md_text))
                if not cfg.keep_attachments:
                    converted_binaries.append(local_path)
            except Exception as e:
                LOG.error("  嵌入转换失败 %s: %s", name, e)
                failed += 1

        if changed:
            try:
                md_path.write_text(body, encoding="utf-8")
                # 写回成功后删除已嵌入的附件原始文件
                if converted_binaries:
                    for bp in converted_binaries:
                        try:
                            bp.unlink()
                            LOG.info("  删除附件文件: %s", bp.name)
                        except OSError as e:
                            LOG.warning("  删除附件文件失败 %s: %s", bp.name, e)
            except OSError as e:
                LOG.warning("写回文档失败 %s: %s", md_path, e)

    LOG.info("Step3 完成: 遇到待嵌入附件 %d，成功嵌入 %d，失败 %d",
             embed_count, embedded, failed)


# ---------------------------------------------------------------------------
# 清理模式：递归删除附件文件
# ---------------------------------------------------------------------------

def clean_all_attachments(root: Path) -> int:
    """递归删除 root 及其所有子目录下的附件文件。

    - 遍历所有层级子目录，删除除 .md 文档外的所有文件（附件原始文件）。
    - 一并清理 .doc 转换遗留的 .convert_tmp 目录（整目录删除，含其内文件）。
    - 不改动任何 .md 文档：已内联进去的 markdown 内容保留。

    返回 0 表示成功，1 表示目标路径无效。
    """
    if not root.exists():
        LOG.error("目录不存在: %s", root)
        return 1
    if not root.is_dir():
        LOG.error("路径不是目录: %s", root)
        return 1

    LOG.info("=== 清理附件 ===")
    LOG.info("目标目录: %s", root)
    LOG.info("保留: *.md 文档；删除: 其余所有文件")

    # 1) 先清理 .doc 转换遗留的 .convert_tmp 目录（整目录删除）
    tmp_removed = 0
    for tmp in [p for p in root.rglob(".convert_tmp") if p.is_dir()]:
        try:
            shutil.rmtree(tmp)
            tmp_removed += 1
            LOG.info("  删除临时目录: %s", tmp)
        except OSError as e:
            LOG.warning("  删除临时目录失败 %s: %s", tmp, e)

    # 2) 递归遍历所有层级子目录，删除非 .md 文件
    targets = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower() != ".md"
    ]
    deleted = 0
    failed = 0
    for p in targets:
        try:
            p.unlink()
            deleted += 1
            LOG.info("  删除附件: %s", os.path.relpath(p, root))
        except OSError as e:
            LOG.warning("  删除失败 %s: %s", p, e)
            failed += 1

    LOG.info(
        "清理完成: 删除附件文件 %d，失败 %d，清理 .convert_tmp 目录 %d",
        deleted, failed, tmp_removed,
    )
    return 0


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    cfg = parse_args(argv)

    # 清理模式：仅递归删除附件文件，不执行同步、不校验凭据
    if cfg.clean_path:
        return clean_all_attachments(cfg.clean_path)

    LOG.info("语雀知识库同步工具启动")
    LOG.info("知识库: %s", cfg.url)
    LOG.info("本地目录: %s", cfg.output)
    if cfg.exclude:
        LOG.info("排除关键字: %s", ", ".join(cfg.exclude))
    LOG.info("Step2 下载附件类型: %s", ", ".join(cfg.attachment_types) or "(无)")
    LOG.info("Step3 嵌入转换类型: %s", ", ".join(cfg.embed_types) or "(无)")
    if cfg.keep_attachments:
        LOG.info("附件处理：embed 类型的附件转 md 嵌入后保留原始文件")
    else:
        LOG.info("附件处理：embed 类型的附件转 md 嵌入后删除原始文件")

    # 预检查：markitdown/xmindparser 缺失即自动 pip 安装，安装失败直接报错退出
    check_tools()

    cfg.output.mkdir(parents=True, exist_ok=True)

    client = YuqueClient(cfg)

    # Step1：文档同步。返回 (本次新增/更新的文档, 所有处理过的文档, 合法key集合, 本地根目录)
    changed_files, all_files, kept_keys, sync_root = sync_step1(client, cfg)

    # Step1.5：本地清理（删除命中exclude的、语雀侧已不存在的孤儿文档及附件、空目录）
    if cfg.no_cleanup:
        LOG.info("=== Step1.5（跳过：--no-cleanup）===")
    else:
        cleanup_local(sync_root, kept_keys, cfg.exclude)

    if not changed_files:
        LOG.info("=== Step2/Step3（跳过：本次无文档变更）===")
        LOG.info("全部同步完成。")
        return 0

    # Step2：下载 attachment_types 类型的附件 + 改写为本地相对路径引用
    sync_step2(client, cfg, changed_files)

    # Step3：把 embed_types 类型的本地附件引用转 md，原地嵌入并删除原引用与附件文件
    if cfg.embed_types:
        sync_step3(cfg, changed_files)
    else:
        LOG.info("=== Step3（跳过：未指定 --embed-types）===")

    LOG.info("全部同步完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())