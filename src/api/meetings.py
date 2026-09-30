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
async def list_meetings(
    search: str = Query("", description="按标题搜索"),
    meeting_type: Optional[str] = Query(None, description="按会议类型过滤"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """列出会议（分页 + 搜索）"""
    db = SessionLocal()
    try:
        q = db.query(Meeting)
        if search:
            q = q.filter(Meeting.title.contains(search))
        if meeting_type:
            q = q.filter(Meeting.meeting_type == meeting_type)
        total = q.count()
        meetings = q.order_by(Meeting.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "records": [
                {
                    "id": m.id,
                    "title": m.title,
                    "meeting_type": m.meeting_type,
                    "background": m.background,
                    "snapshot_ids": json.loads(m.snapshot_ids_json) if m.snapshot_ids_json else [],
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in meetings
            ],
        }
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


@router.delete("/{meeting_id}")
async def delete_meeting(meeting_id: str):
    """删除会议"""
    db = SessionLocal()
    try:
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not m:
            raise HTTPException(status_code=404, detail="会议不存在")
        db.delete(m)
        db.commit()
        return {"deleted": True, "id": meeting_id}
    finally:
        db.close()