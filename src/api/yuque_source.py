"""
语雀来源管理 API

用户可配置多个语雀来源（不同 token 对应不同知识库），拉取文档时选择使用。
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.config import get_config
from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import YuqueSource

config = get_config()
logger = get_logger(__name__)

config = get_config()

logger = get_logger(__name__)

router = APIRouter(prefix="/yuque-sources", tags=["语雀来源"])


class YuqueSourceCreate(BaseModel):
    name: str
    yuque_url: str = ""
    token: str
    session: Optional[str] = ""
    ctoken: Optional[str] = ""
    exclude: Optional[str] = ""
    attachment_types: Optional[str] = ""
    embed_types: Optional[str] = ""


class YuqueSourceUpdate(BaseModel):
    name: Optional[str] = None
    yuque_url: Optional[str] = None
    token: Optional[str] = None
    session: Optional[str] = None
    ctoken: Optional[str] = None
    exclude: Optional[str] = None
    attachment_types: Optional[str] = None
    embed_types: Optional[str] = None


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _source_to_dict(s: YuqueSource) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "yuque_url": s.yuque_url or "",
        "token": s.token[:8] + "***" if s.token else "",
        "has_session": bool(s.session),
        "has_ctoken": bool(s.ctoken),
        "exclude": s.exclude or "",
        "attachment_types": s.attachment_types or "",
        "embed_types": s.embed_types or "",
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("")
async def list_sources(request: Request):
    """列出当前用户的语雀来源"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        sources = (
            db.query(YuqueSource)
            .filter(YuqueSource.user_id == user["user_id"])
            .order_by(YuqueSource.created_at.desc())
            .all()
        )
        return [_source_to_dict(s) for s in sources]
    finally:
        db.close()


@router.post("")
async def create_source(request: Request, body: YuqueSourceCreate):
    """添加语雀来源"""
    user = _get_user(request)
    if not body.name.strip() or not body.token.strip():
        raise HTTPException(status_code=400, detail="名称和 Token 不能为空")

    db = SessionLocal()
    try:
        source = YuqueSource(
            user_id=user["user_id"],
            name=body.name.strip(),
            yuque_url=body.yuque_url.strip(),
            token=body.token.strip(),
            session=body.session or "",
            ctoken=body.ctoken or "",
            exclude=body.exclude or "",
            attachment_types=body.attachment_types or "",
            embed_types=body.embed_types or "",
        )
        db.add(source)
        db.commit()
        db.refresh(source)
        logger.info("语雀来源已添加: %s (user=%s)", source.name, user["username"])
        return _source_to_dict(source)
    finally:
        db.close()


@router.put("/{source_id}")
async def update_source(request: Request, source_id: str, body: YuqueSourceUpdate):
    """更新语雀来源"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        source = (
            db.query(YuqueSource)
            .filter(YuqueSource.id == source_id, YuqueSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")

        if body.name is not None:
            source.name = body.name.strip()
        if body.yuque_url is not None:
            source.yuque_url = body.yuque_url.strip()
        if body.token is not None:
            source.token = body.token.strip()
        if body.session is not None:
            source.session = body.session
        if body.ctoken is not None:
            source.ctoken = body.ctoken
        if body.exclude is not None:
            source.exclude = body.exclude
        if body.attachment_types is not None:
            source.attachment_types = body.attachment_types
        if body.embed_types is not None:
            source.embed_types = body.embed_types

        db.commit()
        return {"updated": True, "id": source_id}
    finally:
        db.close()


@router.delete("/{source_id}")
async def delete_source(request: Request, source_id: str):
    """删除语雀来源"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        source = (
            db.query(YuqueSource)
            .filter(YuqueSource.id == source_id, YuqueSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")

        db.delete(source)
        db.commit()
        logger.info("语雀来源已删除: %s (user=%s)", source.name, user["username"])
        return {"deleted": True, "id": source_id}
    finally:
        db.close()


# ============================================================
# 需求拉取
# ============================================================

class PullRequest(BaseModel):
    requirement_id: str


def do_pull_requirement(source, user: dict, requirement_id: str) -> dict:
    """
    核心拉取逻辑：根据来源和需求号拉取语雀文档。
    返回 { requirement_id, matched_title, total, results }。
    """
    if not source.yuque_url:
        raise HTTPException(status_code=400, detail="来源未配置知识库 URL")

    # 导入 yuque_sync 核心引擎
    import sys
    _scripts_dir = Path(__file__).resolve().parent.parent.parent / "scripts"
    if str(_scripts_dir) not in sys.path:
        sys.path.insert(0, str(_scripts_dir))

    from yuque_sync import Config, YuqueClient, parse_toc, build_tree, doc_is_excluded

    token = source.token or config.YUQUE_API_TOKEN
    session = source.session or config.YUQUE_SESSION
    ctoken = source.ctoken or config.YUQUE_CTOKEN

    if not token:
        raise HTTPException(status_code=500, detail="未配置语雀 Token")

    exclude = [e.strip() for e in (source.exclude or "").split(",") if e.strip()]
    attachment_types = [e.strip() for e in (source.attachment_types or "").split(",") if e.strip()] or ["docx", "pdf", "xls", "xlsx"]
    embed_types = [e.strip() for e in (source.embed_types or "").split(",") if e.strip()] or ["xmind", "xls", "xlsx"]

    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="yuque_pull_"))

    try:
        cfg = Config(
            url=source.yuque_url,
            token=token,
            session=session,
            ctoken=ctoken,
            output=str(tmp_dir),
            exclude=exclude,
            attachment_types=attachment_types,
            embed_types=embed_types,
        )
        client = YuqueClient(cfg)

        repo = client.get_repo()
        toc_yml = repo.get("toc_yml", "")
        if not toc_yml:
            raise HTTPException(status_code=500, detail="知识库 TOC 为空")

        nodes = parse_toc(toc_yml)
        tree = build_tree(nodes)

        from yuque_sync import TocNode
        matched_title = None
        for node in nodes:
            if node.is_dir and requirement_id.upper() in node.title.upper():
                matched_title = node
                break

        if not matched_title:
            raise HTTPException(
                status_code=404,
                detail=f"未找到匹配需求号「{requirement_id}」的节点",
            )

        def collect_docs(node, tree: dict, depth: int = 0) -> list:
            docs = []
            if node.is_doc and not doc_is_excluded(node.title, exclude):
                docs.append(node)
            for child in tree.values():
                if child.parent_uuid == node.uuid:
                    docs.extend(collect_docs(child, tree, depth + 1))
            return docs

        doc_nodes = collect_docs(matched_title, tree)
        logger.info(
            "需求 %s 下找到 %d 个文档: %s",
            requirement_id,
            len(doc_nodes),
            [n.title for n in doc_nodes],
        )

        results = []
        from src.storage.db import SessionLocal as DbSession
        from src.storage.models import Snapshot

        for doc_node in doc_nodes:
            try:
                doc_data = client.get_doc(doc_node.url)
                title = doc_data.get("title", doc_node.title)
                body = doc_data.get("body", "")

                snap_dir = config.resolve_path(config.DATA_DIR) / "snapshots" / "yuque"
                snap_dir.mkdir(parents=True, exist_ok=True)
                content_path = snap_dir / f"{requirement_id}_{doc_node.url}.md"
                content_path.write_text(f"# {title}\n\n{body}", encoding="utf-8")

                raw_path = snap_dir / f"{requirement_id}_{doc_node.url}_raw.json"
                raw_path.write_text(json.dumps(doc_data, ensure_ascii=False, default=str), encoding="utf-8")

                db2 = DbSession()
                try:
                    snap = Snapshot(
                        source_type="yuque",
                        source_url=f"{source.yuque_url}/{doc_node.url}",
                        title=title,
                        content_path=str(content_path),
                        raw_path=str(raw_path),
                        size_bytes=len(body),
                    )
                    db2.add(snap)
                    db2.commit()
                    db2.refresh(snap)
                    results.append({
                        "id": snap.id,
                        "title": title,
                        "slug": doc_node.url,
                        "status": "ok",
                    })
                finally:
                    db2.close()

            except Exception as e:
                logger.error("拉取文档失败: %s — %s", doc_node.title, e)
                results.append({
                    "title": doc_node.title,
                    "slug": doc_node.url,
                    "status": "failed",
                    "error": str(e),
                })

        return {
            "requirement_id": requirement_id,
            "matched_title": matched_title.title,
            "total": len(doc_nodes),
            "results": results,
        }

    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _save_pull_record(db, user: dict, source, requirement_id: str, result: dict) -> str:
    """保存拉取记录到数据库，返回 record_id"""
    from src.storage.models import YuquePullRecord

    success = sum(1 for r in result.get("results", []) if r.get("status") == "ok")
    failed = sum(1 for r in result.get("results", []) if r.get("status") == "failed")

    record = YuquePullRecord(
        user_id=user["user_id"],
        source_id=source.id,
        source_name=source.name,
        requirement_id=requirement_id,
        matched_title=result.get("matched_title", ""),
        total=result.get("total", 0),
        success=success,
        failed=failed,
        results_json=json.dumps(result.get("results", []), ensure_ascii=False),
        status="success" if failed == 0 else "partial" if success > 0 else "failed",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record.id


@router.post("/{source_id}/pull")
async def pull_requirement(request: Request, source_id: str, body: PullRequest):
    """
    拉取指定需求号下的所有语雀文档。
    1. 在知识库 TOC 中搜索需求号匹配的 TITLE 节点
    2. 递归拉取该节点下所有 DOC 文档
    3. 每个文档存为 Snapshot 快照
    4. 自动保存拉取记录
    """
    user = _get_user(request)
    requirement_id = body.requirement_id.strip()
    if not requirement_id:
        raise HTTPException(status_code=400, detail="需求号不能为空")

    # 读取来源
    db = SessionLocal()
    try:
        source = (
            db.query(YuqueSource)
            .filter(YuqueSource.id == source_id, YuqueSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源不存在")
    finally:
        db.close()

    try:
        result = do_pull_requirement(source, user, requirement_id)

        # 保存拉取记录
        db2 = SessionLocal()
        try:
            record_id = _save_pull_record(db2, user, source, requirement_id, result)
            result["record_id"] = record_id
        finally:
            db2.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("拉取需求失败: %s", e)
        raise HTTPException(status_code=500, detail=f"拉取失败: {e}")