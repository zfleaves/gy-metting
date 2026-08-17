"""
文档管理 API (DESIGN.md §3.2)

本地文档上传 + 语雀拉取 + 快照管理。
"""

import json
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel

from src.config import get_config
from src.doc.parser import detect_format, parse
from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import Snapshot

config = get_config()
logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["参考文档"])

MAX_DOC_SIZE_MB = 20


# ============================================================
# 上传本地文档
# ============================================================

@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
):
    """上传本地文档（docx/pdf/txt/md），解析后存入快照"""
    # 读取内容
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > MAX_DOC_SIZE_MB:
        raise HTTPException(status_code=413, detail=f"文件过大: {size_mb:.1f}MB，限制 {MAX_DOC_SIZE_MB}MB")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    filename = file.filename or "unknown"
    ext = detect_format(filename)
    if ext not in ("docx", "pdf", "txt", "md"):
        raise HTTPException(status_code=400, detail=f"不支持格式: .{ext}，支持 docx/pdf/txt/md")

    # 保存原始文件
    doc_dir = config.resolve_path(config.DATA_DIR) / "documents"
    doc_dir.mkdir(parents=True, exist_ok=True)
    doc_id = uuid.uuid4().hex[:16]
    saved_path = doc_dir / f"{doc_id}.{ext}"
    saved_path.write_bytes(content)

    # 解析文本
    try:
        text = parse(str(saved_path))
    except Exception as e:
        saved_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"文档解析失败: {e}")

    # 保存解析后的文本
    content_dir = config.resolve_path(config.DATA_DIR) / "snapshots" / "local"
    content_dir.mkdir(parents=True, exist_ok=True)
    content_path = content_dir / f"{doc_id}.md"
    content_path.write_text(text, encoding="utf-8")

    # 创建快照记录
    db = SessionLocal()
    try:
        snap = Snapshot(
            source_type="local",
            source_url=filename,
            title=filename,
            content_path=str(content_path),
            size_bytes=len(content),
        )
        db.add(snap)
        db.commit()
        db.refresh(snap)
        snapshot_id = snap.id
    finally:
        db.close()

    logger.info("文档上传成功: id=%s, name=%s, size=%d", snapshot_id, filename, len(content))
    return {
        "id": snapshot_id,
        "title": filename,
        "source_type": "local",
        "size_bytes": len(content),
        "preview": text[:500],
    }


# ============================================================
# 语雀拉取
# ============================================================

class YuquePullRequest(BaseModel):
    url: str
    source_id: Optional[str] = None


@router.post("/yuque")
async def pull_yuque(request: Request, body: YuquePullRequest):
    """输入语雀文档 URL，拉取并存入快照。可指定语雀来源。"""
    url = body.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 确定使用的 token
    token = config.YUQUE_API_TOKEN
    session = config.YUQUE_SESSION
    ctoken = config.YUQUE_CTOKEN

    if body.source_id:
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="请先登录")
        db = SessionLocal()
        try:
            from src.storage.models import YuqueSource
            source = (
                db.query(YuqueSource)
                .filter(YuqueSource.id == body.source_id, YuqueSource.user_id == user["user_id"])
                .first()
            )
            if not source:
                raise HTTPException(status_code=404, detail="语雀来源不存在")
            token = source.token or token
            session = source.session or session
            ctoken = source.ctoken or ctoken
        finally:
            db.close()

    # 调用语雀拉取脚本
    try:
        import sys
        _scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
        if str(_scripts_dir) not in sys.path:
            sys.path.insert(0, str(_scripts_dir))

        from yuque_pull import pull_by_url, save_snapshot

        if not token:
            raise HTTPException(status_code=500, detail="未配置语雀 Token，请在 .env 或语雀来源中设置")

        doc = pull_by_url(url, token=token, session=session, ctoken=ctoken)
        snapshot_path = save_snapshot(doc, snapshot_dir=str(config.resolve_path(config.DATA_DIR) / "snapshots" / "yuque"))

        # 创建快照记录
        db = SessionLocal()
        try:
            snap = Snapshot(
                source_type="yuque",
                source_url=url,
                title=doc.get("title", "语雀文档"),
                content_path=str(snapshot_path / "snapshot.md"),
                raw_path=str(snapshot_path / "snapshot_raw.json"),
                size_bytes=len(doc.get("body", "")),
            )
            db.add(snap)
            db.commit()
            db.refresh(snap)
            snapshot_id = snap.id
        finally:
            db.close()

        logger.info("语雀拉取成功: id=%s, title=%s", snapshot_id, doc.get("title"))
        return {
            "id": snapshot_id,
            "title": doc.get("title"),
            "source_type": "yuque",
            "source_url": url,
            "preview": doc.get("body", "")[:500],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("语雀拉取失败: %s", e)
        raise HTTPException(status_code=500, detail=f"语雀拉取失败: {e}")


# ============================================================
# 快照列表 & 详情 & 删除
# ============================================================

@router.get("")
async def list_documents():
    """列出所有快照"""
    db = SessionLocal()
    try:
        snaps = db.query(Snapshot).order_by(Snapshot.created_at.desc()).limit(50).all()
        return [
            {
                "id": s.id,
                "title": s.title,
                "source_type": s.source_type,
                "source_url": s.source_url,
                "size_bytes": s.size_bytes,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in snaps
        ]
    finally:
        db.close()


@router.get("/{doc_id}")
async def get_document(doc_id: str):
    """获取快照详情（含完整文本内容）"""
    db = SessionLocal()
    try:
        snap = db.query(Snapshot).filter(Snapshot.id == doc_id).first()
        if not snap:
            raise HTTPException(status_code=404, detail="文档不存在")

        content = ""
        if snap.content_path and os.path.exists(snap.content_path):
            content = Path(snap.content_path).read_text(encoding="utf-8")

        return {
            "id": snap.id,
            "title": snap.title,
            "source_type": snap.source_type,
            "source_url": snap.source_url,
            "size_bytes": snap.size_bytes,
            "content": content,
            "created_at": snap.created_at.isoformat() if snap.created_at else None,
        }
    finally:
        db.close()


@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """删除快照及其关联文件"""
    db = SessionLocal()
    try:
        snap = db.query(Snapshot).filter(Snapshot.id == doc_id).first()
        if not snap:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 删除关联文件
        for path_attr in ("content_path", "raw_path"):
            filepath = getattr(snap, path_attr, None)
            if filepath and os.path.exists(filepath):
                os.remove(filepath)

        db.delete(snap)
        db.commit()
        return {"deleted": True, "id": doc_id}
    finally:
        db.close()