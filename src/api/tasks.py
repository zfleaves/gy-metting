"""
任务 API (DESIGN.md §3.6)

任务提交：POST /api/tasks
任务查询：GET /api/tasks/{task_id}
任务列表：GET /api/tasks
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.log_utils import get_logger
from src.storage.models import TaskType
from src.task.queue import get_task_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务管理"])


@router.post("")
async def submit_task(
    task_type: str = Query(..., description="任务类型: asr | minutes | yuque_pull"),
    audio_path: Optional[str] = Query(None, description="音频文件路径（ASR 任务）"),
    meeting_id: Optional[str] = Query(None, description="关联会议 ID"),
):
    """
    提交异步任务。

    返回 task_id，前端轮询 GET /api/tasks/{task_id} 获取结果。
    """
    # 校验任务类型
    try:
        tt = TaskType(task_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的任务类型: {task_type}，可选: asr, minutes, yuque_pull",
        )

    # 构建参数
    params = {}
    if audio_path:
        params["audio_path"] = audio_path

    manager = get_task_manager()
    try:
        task_id = await manager.submit(tt, params, meeting_id=meeting_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"task_id": task_id, "status": "pending"}


@router.get("/{task_id}")
async def get_task(task_id: str):
    """查询任务状态与结果"""
    manager = get_task_manager()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return task


@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None, description="按状态筛选: pending/processing/completed/failed"),
    task_type: Optional[str] = Query(None, description="按类型筛选: asr/minutes/yuque_pull"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """列出任务（分页）"""
    manager = get_task_manager()
    return manager.list_tasks(status=status, task_type=task_type, limit=limit, offset=offset)