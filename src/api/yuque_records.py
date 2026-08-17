"""
语雀拉取记录 API

每次拉取需求后自动保存记录，支持查看历史、删除、重新拉取。
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from src.config import get_config
from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import YuquePullRecord, YuqueSource

config = get_config()
logger = get_logger(__name__)

router = APIRouter(prefix="/yuque-records", tags=["语雀拉取记录"])


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _record_to_dict(r: YuquePullRecord) -> dict:
    return {
        "id": r.id,
        "source_id": r.source_id,
        "source_name": r.source_name,
        "requirement_id": r.requirement_id,
        "matched_title": r.matched_title or "",
        "total": r.total,
        "success": r.success,
        "failed": r.failed,
        "results": json.loads(r.results_json) if r.results_json else [],
        "status": r.status,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }


@router.get("")
async def list_records(request: Request):
    """列出当前用户的所有拉取记录（按时间倒序）"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        records = (
            db.query(YuquePullRecord)
            .filter(YuquePullRecord.user_id == user["user_id"])
            .order_by(YuquePullRecord.created_at.desc())
            .limit(100)
            .all()
        )
        return [_record_to_dict(r) for r in records]
    finally:
        db.close()


@router.get("/{record_id}")
async def get_record(request: Request, record_id: str):
    """获取单条拉取记录详情"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        record = (
            db.query(YuquePullRecord)
            .filter(YuquePullRecord.id == record_id, YuquePullRecord.user_id == user["user_id"])
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        return _record_to_dict(record)
    finally:
        db.close()


@router.delete("/{record_id}")
async def delete_record(request: Request, record_id: str):
    """删除拉取记录"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        record = (
            db.query(YuquePullRecord)
            .filter(YuquePullRecord.id == record_id, YuquePullRecord.user_id == user["user_id"])
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")
        db.delete(record)
        db.commit()
        logger.info("拉取记录已删除: %s (user=%s)", record.requirement_id, user["username"])
        return {"deleted": True, "id": record_id}
    finally:
        db.close()


@router.post("/{record_id}/re-pull")
async def re_pull_record(request: Request, record_id: str):
    """重新拉取：复用原来源 + 需求号，更新记录"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        record = (
            db.query(YuquePullRecord)
            .filter(YuquePullRecord.id == record_id, YuquePullRecord.user_id == user["user_id"])
            .first()
        )
        if not record:
            raise HTTPException(status_code=404, detail="记录不存在")

        source = (
            db.query(YuqueSource)
            .filter(YuqueSource.id == record.source_id, YuqueSource.user_id == user["user_id"])
            .first()
        )
        if not source:
            raise HTTPException(status_code=404, detail="来源已被删除，无法重新拉取")
    finally:
        db.close()

    # 调用 pull_requirement 逻辑（复用 yuque_source 中的拉取函数）
    from src.api.yuque_source import do_pull_requirement

    try:
        result = do_pull_requirement(
            source=source,
            user=user,
            requirement_id=record.requirement_id,
        )

        # 更新记录
        db2 = SessionLocal()
        try:
            rec = db2.query(YuquePullRecord).filter(YuquePullRecord.id == record_id).first()
            if rec:
                rec.matched_title = result.get("matched_title", rec.matched_title)
                rec.total = result.get("total", 0)
                rec.success = sum(1 for r in result.get("results", []) if r.get("status") == "ok")
                rec.failed = sum(1 for r in result.get("results", []) if r.get("status") == "failed")
                rec.results_json = json.dumps(result.get("results", []), ensure_ascii=False)
                rec.status = "success" if rec.failed == 0 else "partial" if rec.success > 0 else "failed"
                db2.commit()
                db2.refresh(rec)
                result["record_id"] = rec.id
        finally:
            db2.close()

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("重新拉取失败: %s", e)
        raise HTTPException(status_code=500, detail=f"重新拉取失败: {e}")