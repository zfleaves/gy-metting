"""
统计数据 API (DESIGN.md §2.1)

提供仪表盘所需的聚合统计数据。
"""

from fastapi import APIRouter, Request

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import Minutes, Task, Meeting

logger = get_logger(__name__)

router = APIRouter(prefix="/stats", tags=["统计数据"])


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    return user or {}


@router.get("")
async def get_stats(request: Request):
    """获取仪表盘统计数据"""
    user = _get_user(request)
    user_id = user.get("user_id")
    is_admin = user.get("role") in ("super_admin", "admin")

    db = SessionLocal()
    try:
        # 任务统计
        task_q = db.query(Task)
        if not is_admin and user_id:
            task_q = task_q.filter(Task.user_id == user_id)

        stats = {
            "tasks": {
                "total": task_q.count(),
                "completed": task_q.filter(Task.status == "completed").count(),
                "processing": task_q.filter(Task.status == "processing").count(),
                "pending": task_q.filter(Task.status == "pending").count(),
                "failed": task_q.filter(Task.status == "failed").count(),
            },
            "minutes": {
                "total": db.query(Minutes).count(),
            },
            "meetings": {
                "total": db.query(Meeting).count(),
            },
        }

        return stats
    finally:
        db.close()