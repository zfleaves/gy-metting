"""
纪要偏好管理 API

- 未采纳（候选版本）：每次生成自动保存，用户可对比挑选
- 已采纳（偏好库）：从候选采纳而来，后续生成可选用
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import MinutesPreference

logger = get_logger(__name__)

router = APIRouter(prefix="/preferences", tags=["纪要偏好"])


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _to_dict(p: MinutesPreference) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "meeting_type": p.meeting_type,
        "content": p.content,
        "temperature": p.temperature,
        "max_tokens": p.max_tokens,
        "custom_prompt": p.custom_prompt,
        "notes": p.notes,
        "is_adopted": p.is_adopted == "1",
        "is_default": p.is_default == "1",
        "source_minutes_id": p.source_minutes_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


@router.get("")
async def list_preferences(
    request: Request,
    adopted: Optional[str] = Query(None, description="过滤: 1=已采纳, 0=未采纳"),
    meeting_type: Optional[str] = Query(None, description="按会议类型过滤"),
    limit: int = Query(50, ge=1, le=200),
):
    """列出偏好列表（按是否采纳分区）"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        q = db.query(MinutesPreference).filter(MinutesPreference.user_id == user["user_id"])
        if adopted is not None:
            q = q.filter(MinutesPreference.is_adopted == adopted)
        if meeting_type:
            q = q.filter(MinutesPreference.meeting_type == meeting_type)
        q = q.order_by(MinutesPreference.created_at.desc()).limit(limit)
        return {"preferences": [_to_dict(p) for p in q.all()]}
    finally:
        db.close()


@router.post("")
async def create_preference(request: Request):
    """创建偏好（从生成结果自动保存为候选版本）"""
    user = _get_user(request)
    body = await request.json()

    pref = MinutesPreference(
        user_id=user["user_id"],
        name=body.get("name"),
        meeting_type=body.get("meeting_type", "通用"),
        content=body.get("content"),
        temperature=body.get("temperature"),
        max_tokens=body.get("max_tokens"),
        custom_prompt=body.get("custom_prompt"),
        notes=body.get("notes"),
        is_adopted=body.get("is_adopted", "0"),
        is_default="0",
        source_minutes_id=body.get("source_minutes_id"),
    )
    db = SessionLocal()
    try:
        db.add(pref)
        db.commit()
        db.refresh(pref)
        return _to_dict(pref)
    finally:
        db.close()


@router.put("/{pref_id}")
async def update_preference(request: Request, pref_id: str):
    """更新偏好（名称、采纳状态、默认标记等）"""
    user = _get_user(request)
    body = await request.json()
    db = SessionLocal()
    try:
        p = db.query(MinutesPreference).filter(
            MinutesPreference.id == pref_id,
            MinutesPreference.user_id == user["user_id"],
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="偏好不存在")

        if "name" in body:
            p.name = body["name"]
        if "meeting_type" in body:
            p.meeting_type = body["meeting_type"]
        if "content" in body:
            p.content = body["content"]
        if "temperature" in body:
            p.temperature = body["temperature"]
        if "max_tokens" in body:
            p.max_tokens = body["max_tokens"]
        if "custom_prompt" in body:
            p.custom_prompt = body["custom_prompt"]
        if "notes" in body:
            p.notes = body["notes"]

        # 采纳操作：将某个候选设为已采纳，同时清除其他已采纳的默认标记
        if body.get("adopt") is True:
            p.is_adopted = "1"
        if body.get("set_default") is True:
            # 先清除该用户所有默认
            db.query(MinutesPreference).filter(
                MinutesPreference.user_id == user["user_id"],
                MinutesPreference.is_default == "1",
            ).update({"is_default": "0"})
            p.is_default = "1"

        db.commit()
        db.refresh(p)
        return _to_dict(p)
    finally:
        db.close()


@router.delete("/{pref_id}")
async def delete_preference(request: Request, pref_id: str):
    """删除偏好"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        p = db.query(MinutesPreference).filter(
            MinutesPreference.id == pref_id,
            MinutesPreference.user_id == user["user_id"],
        ).first()
        if not p:
            raise HTTPException(status_code=404, detail="偏好不存在")
        db.delete(p)
        db.commit()
        return {"deleted": True, "id": pref_id}
    finally:
        db.close()