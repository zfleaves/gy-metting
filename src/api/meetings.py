"""
会议管理 API (DESIGN.md §3.5)

创建会议、录入业务背景、关联参考文档。
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import Meeting

config = None  # lazy import
logger = get_logger(__name__)

router = APIRouter(prefix="/meetings", tags=["会议管理"])


class MeetingCreate(BaseModel):
    title: Optional[str] = ""
    background: Optional[str] = ""
    meeting_type: Optional[str] = "需求评审"
    snapshot_ids: Optional[list[str]] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    background: Optional[str] = None
    snapshot_ids: Optional[list[str]] = None


@router.post("")
async def create_meeting(request: Request, body: MeetingCreate):
    """创建会议（含业务背景和关联文档）"""
    db = SessionLocal()
    try:
        meeting = Meeting(
            title=body.title or "未命名会议",
            meeting_type=body.meeting_type or "需求评审",
            background=body.background or "",
            snapshot_ids_json=json.dumps(body.snapshot_ids) if body.snapshot_ids else None,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)

        return {
            "id": meeting.id,
            "title": meeting.title,
            "meeting_type": meeting.meeting_type,
            "background": meeting.background,
            "snapshot_ids": body.snapshot_ids or [],
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        }
    finally:
        db.close()


@router.get("")
async def list_meetings():
    """列出所有会议"""
    db = SessionLocal()
    try:
        meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).limit(20).all()
        return [
            {
                "id": m.id,
                "title": m.title,
                "meeting_type": m.meeting_type,
                "background": m.background,
                "snapshot_ids": json.loads(m.snapshot_ids_json) if m.snapshot_ids_json else [],
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in meetings
        ]
    finally:
        db.close()


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str):
    """获取会议详情"""
    db = SessionLocal()
    try:
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="会议不存在")

        # 加载关联的快照内容
        snapshots = []
        snapshot_ids = json.loads(m.snapshot_ids_json) if m.snapshot_ids_json else []
        if snapshot_ids:
            from src.storage.models import Snapshot
            for sid in snapshot_ids:
                snap = db.query(Snapshot).filter(Snapshot.id == sid).first()
                if snap:
                    snapshots.append({
                        "id": snap.id,
                        "title": snap.title,
                        "source_type": snap.source_type,
                    })

        return {
            "id": m.id,
            "title": m.title,
            "meeting_type": m.meeting_type,
            "background": m.background,
            "snapshot_ids": snapshot_ids,
            "snapshots": snapshots,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
        }
    finally:
        db.close()


@router.put("/{meeting_id}")
async def update_meeting(meeting_id: str, body: MeetingUpdate):
    """更新会议（修改背景、关联文档等）"""
    db = SessionLocal()
    try:
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="会议不存在")

        if body.title is not None:
            m.title = body.title
        if body.background is not None:
            m.background = body.background
        if body.snapshot_ids is not None:
            m.snapshot_ids_json = json.dumps(body.snapshot_ids)

        db.commit()
        return {"updated": True, "id": meeting_id}
    finally:
        db.close()