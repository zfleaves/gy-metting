"""
任务 API (DESIGN.md §3.6)

任务提交：POST /api/tasks
任务查询：GET /api/tasks/{task_id}
任务列表：GET /api/tasks
分段数据：GET /api/tasks/{task_id}/segments
"""

import json
import os
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


@router.get("/{task_id}/segments")
async def get_task_segments(task_id: str):
    """获取任务的分段数据（从 JSON 文件读取，避免 DB 截断）"""
    manager = get_task_manager()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    result_summary = task.get("result_summary")
    if not result_summary:
        raise HTTPException(status_code=404, detail="任务无结果")

    try:
        summary = json.loads(result_summary)
        segments_path = summary.get("segments_path")
    except json.JSONDecodeError:
        raise HTTPException(status_code=404, detail="结果解析失败")

    if not segments_path or not os.path.exists(segments_path):
        raise HTTPException(status_code=404, detail="分段文件不存在")

    with open(segments_path, "r", encoding="utf-8") as f:
        segments = json.load(f)

    return {"task_id": task_id, "segments": segments, "segments_count": len(segments)}


@router.post("/{task_id}/highlights")
async def save_highlights(task_id: str, body: dict):
    """保存重点语句标记（{highlighted_indices: [0, 3, 5]}）"""
    manager = get_task_manager()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    result_summary = task.get("result_summary")
    if not result_summary:
        raise HTTPException(status_code=404, detail="任务无结果")

    try:
        summary = json.loads(result_summary)
        segments_path = summary.get("segments_path")
    except json.JSONDecodeError:
        raise HTTPException(status_code=404, detail="结果解析失败")

    if not segments_path:
        raise HTTPException(status_code=404, detail="分段文件不存在")

    # 保存高亮标记到同目录
    highlights_path = os.path.join(os.path.dirname(segments_path), f"{task_id}_highlights.json")
    indices = body.get("highlighted_indices", [])
    with open(highlights_path, "w", encoding="utf-8") as f:
        json.dump({"highlighted_indices": indices}, f, ensure_ascii=False)

    return {"highlighted_indices": indices, "saved": True}


@router.get("/{task_id}/highlights")
async def get_highlights(task_id: str):
    """获取重点语句标记"""
    manager = get_task_manager()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    result_summary = task.get("result_summary")
    if not result_summary:
        return {"highlighted_indices": []}

    try:
        summary = json.loads(result_summary)
        segments_path = summary.get("segments_path")
    except json.JSONDecodeError:
        return {"highlighted_indices": []}

    if not segments_path:
        return {"highlighted_indices": []}

    highlights_path = os.path.join(os.path.dirname(segments_path), f"{task_id}_highlights.json")
    if not os.path.exists(highlights_path):
        return {"highlighted_indices": []}

    with open(highlights_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {"highlighted_indices": data.get("highlighted_indices", [])}


@router.get("/{task_id}/auto-highlight-keywords")
async def get_auto_highlight_keywords(task_id: str):
    """获取自动标记关键词和忽略关键词（从配置读取）"""
    from src.config import get_config
    config = get_config()
    return {
        "keywords": config.auto_highlight_keywords,
        "ignore_keywords": config.auto_ignore_keywords,
    }


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