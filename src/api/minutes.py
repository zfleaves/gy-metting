"""
AI 纪要生成与管理 API (DESIGN.md §3.3)

- 流式生成纪要（SSE）
- 纪要记录管理（列表/详情/删除/导出）
"""

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse, StreamingResponse

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import Meeting, Minutes, MinutesPreference

logger = get_logger(__name__)

router = APIRouter(prefix="/minutes", tags=["AI 纪要"])


def _get_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="请先登录")
    return user


def _to_dict(m: Minutes) -> dict:
    # 加载关联的任务和会议名称
    task_name = None
    meeting_title = None
    meeting_id = m.meeting_id
    db = SessionLocal()
    try:
        if m.task_id:
            from src.storage.models import Task
            task = db.query(Task).filter(Task.id == m.task_id).first()
            if task:
                task_name = task.name
                # 如果纪要没有meeting_id，从任务取
                if not meeting_id and task.meeting_id:
                    meeting_id = task.meeting_id
        if meeting_id:
            from src.storage.models import Meeting
            meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
            if meeting:
                meeting_title = meeting.title
    finally:
        db.close()

    return {
        "id": m.id,
        "meeting_id": meeting_id,
        "task_id": m.task_id,
        "title": m.title,
        "meeting_type": m.meeting_type or "通用",
        "task_name": task_name,
        "meeting_title": meeting_title,
        "content": m.content,
        "token_count": m.token_count or 0,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


@router.get("")
async def list_minutes(
    request: Request,
    search: str = Query("", description="搜索标题"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """列出纪要记录（分页）"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        q = db.query(Minutes).filter(Minutes.user_id == user["user_id"])
        if search:
            q = q.filter(Minutes.title.contains(search))
        total = q.count()
        records = q.order_by(Minutes.created_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "records": [_to_dict(r) for r in records],
        }
    finally:
        db.close()


@router.get("/generate")
async def generate_minutes(
    request: Request,
    task_id: str = Query(..., description="任务 ID（ASR 转写任务）"),
    meeting_type: Optional[str] = Query(None, description="会议类型"),
    custom_prompt: Optional[str] = Query(None, description="自定义提示词"),
    temperature: float = Query(0.3, ge=0.0, le=2.0),
    max_tokens: int = Query(8192, ge=256, le=32768),
    preference_id: Optional[str] = Query(None, description="使用的偏好 ID"),
    regenerate_reason: Optional[str] = Query(None, description="重新生成原因"),
    regenerate_notes: Optional[str] = Query(None, description="重新生成注意事项"),
):
    """SSE 流式生成 AI 纪要，完成后自动保存记录"""
    user = _get_user(request)

    async def event_stream():
        full_text = ""
        total_tokens = 0
        title = ""
        meeting_type_val = meeting_type or "通用"
        prompt_used = ""

        try:
            from src.llm.context import build_messages
            # 如果传入了偏好，加载偏好内容作为额外上下文
            extra_context = ""
            if preference_id:
                db_ctx = SessionLocal()
                try:
                    pref = db_ctx.query(MinutesPreference).filter(
                        MinutesPreference.id == preference_id,
                        MinutesPreference.user_id == user["user_id"],
                    ).first()
                    if pref and pref.content:
                        extra_context = f"\n\n【参考偏好模板】\n以下是一个你之前生成的、用户采纳的偏好纪要格式，请参考其风格和结构：\n\n{pref.content[:2000]}"
                finally:
                    db_ctx.close()

            messages = build_messages(
                task_id=task_id,
                custom_prompt=custom_prompt,
                meeting_type=meeting_type,
                extra_context=extra_context,
                regenerate_reason=regenerate_reason,
                regenerate_notes=regenerate_notes,
            )
            prompt_used = messages[0]["content"] if messages else ""

            from src.llm.adapter import get_llm_adapter
            adapter = get_llm_adapter()

            yield f"data: {json.dumps({'type': 'start', 'message': '开始生成纪要...'})}\n\n"

            async for chunk in adapter.chat(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            ):
                if chunk:
                    full_text += chunk
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            total_tokens = adapter.count_tokens(full_text)

            # 提取标题
            for line in full_text.split("\n"):
                line = line.strip()
                if line.startswith("**会议主题**") or line.startswith("- **会议主题**"):
                    title = line.split("：", 1)[-1].strip() if "：" in line else line.split("**", 2)[-1].strip()
                    break
            if not title:
                title = f"AI 纪要 {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"

            # 保存到数据库
            db = SessionLocal()
            try:
                # 从任务获取关联的会议 ID
                task_meeting_id = None
                from src.storage.models import Task as TaskModel
                task_obj = db.query(TaskModel).filter(TaskModel.id == task_id).first()
                if task_obj:
                    task_meeting_id = task_obj.meeting_id

                record = Minutes(
                    user_id=user["user_id"],
                    task_id=task_id,
                    meeting_id=task_meeting_id,
                    title=title,
                    meeting_type=meeting_type_val,
                    content=full_text,
                    prompt=prompt_used,
                    token_count=total_tokens,
                )
                db.add(record)
                db.commit()
                db.refresh(record)
                record_id = record.id

                # 自动保存到未采纳偏好池
                pref = MinutesPreference(
                    user_id=user["user_id"],
                    name=f"候选-{title[:20]}",
                    meeting_type=meeting_type_val,
                    content=full_text,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    custom_prompt=custom_prompt,
                    notes=regenerate_reason or "",
                    is_adopted="0",
                    source_minutes_id=record_id,
                )
                db.add(pref)
                db.commit()
                db.refresh(pref)
                pref_id = pref.id
            finally:
                db.close()

            yield f"data: {json.dumps({'type': 'done', 'text': full_text, 'id': record_id, 'preference_id': pref_id, 'title': title, 'usage': {'total_tokens': total_tokens}})}\n\n"

        except Exception as e:
            logger.error("纪要生成失败: %s", e, exc_info=True)
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{minutes_id}")
async def get_minutes(request: Request, minutes_id: str):
    """获取单条纪要详情"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(Minutes).filter(Minutes.id == minutes_id, Minutes.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="纪要不存在")
        return _to_dict(m)
    finally:
        db.close()


@router.delete("/{minutes_id}")
async def delete_minutes(request: Request, minutes_id: str):
    """删除纪要记录"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(Minutes).filter(Minutes.id == minutes_id, Minutes.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="纪要不存在")
        db.delete(m)
        db.commit()
        return {"deleted": True, "id": minutes_id}
    finally:
        db.close()


@router.put("/{minutes_id}")
async def update_minutes(request: Request, minutes_id: str):
    """更新纪要内容（手动编辑后保存）"""
    user = _get_user(request)
    body = await request.json()
    new_content = body.get("content")
    new_title = body.get("title")

    if not new_content:
        raise HTTPException(status_code=400, detail="内容不能为空")

    db = SessionLocal()
    try:
        m = db.query(Minutes).filter(Minutes.id == minutes_id, Minutes.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="纪要不存在")
        m.content = new_content
        if new_title:
            m.title = new_title
        db.commit()
        db.refresh(m)
        return _to_dict(m)
    finally:
        db.close()


@router.get("/{minutes_id}/export")
async def export_minutes(request: Request, minutes_id: str):
    """导出纪要 Markdown 文件"""
    user = _get_user(request)
    db = SessionLocal()
    try:
        m = db.query(Minutes).filter(Minutes.id == minutes_id, Minutes.user_id == user["user_id"]).first()
        if not m:
            raise HTTPException(status_code=404, detail="纪要不存在")
        filename = f"{m.title or '会议纪要'}.md"
        content = m.content or "(无内容)"
        return PlainTextResponse(
            content=content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    finally:
        db.close()