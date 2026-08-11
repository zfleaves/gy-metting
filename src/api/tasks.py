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

from fastapi import APIRouter, HTTPException, Query, Request

from src.log_utils import get_logger
from src.storage.models import TaskType
from src.task.queue import get_task_manager

logger = get_logger(__name__)

router = APIRouter(prefix="/tasks", tags=["任务管理"])


@router.post("")
async def submit_task(
    request: Request,
    task_type: str = Query(..., description="任务类型: asr | minutes | yuque_pull"),
    audio_path: Optional[str] = Query(None, description="音频文件路径（ASR 任务）"),
    meeting_id: Optional[str] = Query(None, description="关联会议 ID"),
):
    """
    提交异步任务。相同音频文件复用已有转写结果。

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

    # 获取当前用户
    user = getattr(request.state, "user", None)
    user_id = user["user_id"] if user else None

    # 构建参数
    params = {}
    if audio_path:
        params["audio_path"] = audio_path

    # 去重：检查是否已有相同音频的已完成任务
    if audio_path and tt == TaskType.ASR:
        manager = get_task_manager()
        existing_tasks = manager.list_tasks(status="completed", task_type="asr", limit=100)
        for t in existing_tasks:
            try:
                summary = json.loads(t.get("result_summary", "{}"))
                if summary.get("audio_path") == audio_path:
                    logger.info("复用已有转写结果: task_id=%s, audio=%s", t["id"], audio_path)
                    return {"task_id": t["id"], "status": "completed", "reused": True}
            except (json.JSONDecodeError, KeyError):
                continue

    manager = get_task_manager()
    try:
        task_id = await manager.submit(tt, params, meeting_id=meeting_id, user_id=user_id)
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


# ============================================================
# 用户自学习 API
# ============================================================

@router.post("/corrections")
async def add_correction(body: dict):
    """添加文字更正：{wrong: "错词", correct: "正确词"}"""
    from src.storage.user_data import add_correction
    wrong = body.get("wrong", "").strip()
    correct = body.get("correct", "").strip()
    if not wrong or not correct:
        raise HTTPException(status_code=400, detail="wrong 和 correct 不能为空")
    corrections = add_correction(wrong, correct)
    return {"corrections": corrections, "count": len(corrections)}


@router.get("/corrections")
async def list_corrections():
    """获取所有文字更正记录"""
    from src.storage.user_data import get_corrections
    corrections = get_corrections()
    return {"corrections": corrections, "count": len(corrections)}


@router.delete("/corrections")
async def delete_correction(body: dict):
    """删除文字更正：{wrong: "错词"}"""
    from src.storage.user_data import remove_correction
    wrong = body.get("wrong", "").strip()
    if not wrong:
        raise HTTPException(status_code=400, detail="wrong 不能为空")
    corrections = remove_correction(wrong)
    return {"corrections": corrections, "count": len(corrections)}


@router.post("/fluff")
async def add_fluff(body: dict):
    """添加废话标记：{text: "废话文本"}"""
    from src.storage.user_data import add_fluff_pattern
    text = body.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text 不能为空")
    patterns = add_fluff_pattern(text)
    return {"patterns": patterns, "count": len(patterns)}


@router.get("/fluff")
async def list_fluff():
    """获取所有废话模式"""
    from src.storage.user_data import get_fluff_patterns
    patterns = get_fluff_patterns()
    return {"patterns": patterns, "count": len(patterns)}


@router.get("/{task_id}")
async def get_task(request: Request, task_id: str):
    """查询任务状态与结果"""
    manager = get_task_manager()
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")

    # 权限检查：用户只能看自己的任务，管理员可看全部
    user = getattr(request.state, "user", None)
    if user and user["role"] not in ("super_admin", "admin"):
        if task.get("user_id") and task["user_id"] != user["user_id"]:
            raise HTTPException(status_code=403, detail="无权访问此任务")

    return task


@router.get("")
async def list_tasks(
    request: Request,
    status: Optional[str] = Query(None, description="按状态筛选: pending/processing/completed/failed"),
    task_type: Optional[str] = Query(None, description="按类型筛选: asr/minutes/yuque_pull"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """列出任务（分页），按用户隔离"""
    user = getattr(request.state, "user", None)
    manager = get_task_manager()

    # 普通用户只看自己的任务
    if user and user["role"] not in ("super_admin", "admin"):
        from src.task.queue import list_tasks_by_user
        return list_tasks_by_user(user["user_id"], status=status, task_type=task_type, limit=limit, offset=offset)

    return manager.list_tasks(status=status, task_type=task_type, limit=limit, offset=offset)