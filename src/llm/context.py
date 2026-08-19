"""
上下文组装引擎 (DESIGN.md §3.3.2)

将会议信息（业务背景、参考文档、转写文本）组装为 LLM 调用所需的上下文。
"""

import json
from pathlib import Path
from typing import Optional

from src.log_utils import get_logger
from src.storage.db import SessionLocal
from src.storage.models import Meeting, Snapshot, Task

logger = get_logger(__name__)


def load_task_context(task_id: str) -> dict:
    """
    根据任务 ID 加载上下文，自动从关联会议获取业务背景和参考文档。

    Args:
        task_id: 任务 ID

    Returns:
        {
            "title": str,
            "meeting_type": str,
            "background": str,
            "documents": [{"title": str, "content": str}],
            "transcript": str,
            "task_name": str,
        }
    """
    db = SessionLocal()
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        # 加载转写文本
        transcript = _load_transcript(task)

        # 加载关联会议
        meeting_title = task.name or ""
        meeting_type = "通用"
        background = ""
        documents = []

        if task.meeting_id:
            meeting = db.query(Meeting).filter(Meeting.id == task.meeting_id).first()
            if meeting:
                meeting_title = meeting.title or task.name or ""
                meeting_type = meeting.meeting_type or "通用"
                background = meeting.background or ""

                # 加载参考文档快照
                snapshot_ids = []
                if meeting.snapshot_ids_json:
                    try:
                        snapshot_ids = json.loads(meeting.snapshot_ids_json)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning("解析 snapshot_ids_json 失败: meeting_id=%s", meeting.id)
                for sid in snapshot_ids:
                    snap = db.query(Snapshot).filter(Snapshot.id == sid).first()
                    if snap and snap.content_path:
                        try:
                            content = Path(snap.content_path).read_text(encoding="utf-8", errors="replace")
                            if len(content) > 5000:
                                content = content[:5000] + f"\n\n...（文档过长，已截断，原文共 {len(content)} 字）"
                            documents.append({
                                "title": snap.title,
                                "content": content,
                            })
                        except Exception as e:
                            logger.warning("读取快照失败: %s — %s", snap.content_path, e)

        return {
            "title": meeting_title,
            "meeting_type": meeting_type,
            "background": background,
            "documents": documents,
            "transcript": transcript,
            "task_name": task.name or task_id[:8],
        }
    finally:
        db.close()


def _load_transcript(task: Task) -> str:
    """从任务中加载转写文本"""
    if task.result_summary:
        try:
            summary = json.loads(task.result_summary)
            text = summary.get("text_preview", "") or summary.get("full_text", "")
            if text:
                if len(text) > 30000:
                    text = text[:30000] + f"\n\n...（转写文本过长，已截断，原文共 {len(text)} 字）"
                return text
        except (json.JSONDecodeError, KeyError):
            pass

    # 尝试从 result_path 读取
    if task.result_path and Path(task.result_path).exists():
        try:
            text = Path(task.result_path).read_text(encoding="utf-8", errors="replace")
            if len(text) > 30000:
                text = text[:30000] + f"\n\n...（转写文本过长，已截断）"
            return text
        except Exception:
            pass

    return task.result_summary[:30000] if task.result_summary else ""


def build_messages(
    task_id: str,
    custom_prompt: Optional[str] = None,
    meeting_type: Optional[str] = None,
    extra_context: Optional[str] = None,
    regenerate_reason: Optional[str] = None,
    regenerate_notes: Optional[str] = None,
) -> list[dict]:
    """
    组装完整的消息列表，用于 LLM 调用。

    Args:
        task_id: 任务 ID
        custom_prompt: 自定义提示词（覆盖系统模板）
        meeting_type: 会议类型（用于选择模板）
        extra_context: 额外上下文（如偏好模板）
        regenerate_reason: 重新生成原因
        regenerate_notes: 重新生成注意事项

    Returns:
        OpenAI 格式消息列表
    """
    ctx = load_task_context(task_id)

    # 选择系统模板
    if custom_prompt:
        system_content = custom_prompt
    else:
        from src.llm.templates import get_system_template
        template_type = meeting_type or ctx["meeting_type"]
        system_content = get_system_template(
            template_type,
            meeting_title=ctx["title"],
            background=ctx["background"],
        )

    # 构建参考文档块
    doc_blocks = []
    for d in ctx["documents"]:
        doc_blocks.append(f"### {d['title']}\n\n{d['content']}")
    docs_text = "\n\n---\n\n".join(doc_blocks) if doc_blocks else ""

    # 构建分层消息列表，让 LLM 清晰区分信息优先级
    messages = []

    # 第一部分：系统提示词（角色定义 + 输出格式）
    messages.append({"role": "system", "content": system_content})

    # 第二部分：业务背景（低优先级，仅做上下文参考）
    bg_msg = f"## 业务背景\n\n{ctx['background'] or '无'}"
    messages.append({"role": "user", "content": bg_msg})
    messages.append({"role": "assistant", "content": "已收到业务背景信息。"})

    # 第三部分：参考文档（中优先级，有则参考，无则跳过）
    if docs_text:
        doc_msg = f"## 参考文档\n\n{docs_text}\n\n注意：文档内容仅作为业务基线，会上未讨论的内容严禁输出评审结论。"
        messages.append({"role": "user", "content": doc_msg})
        messages.append({"role": "assistant", "content": "已收到参考文档，将作为业务基线参考。"})

    # 第四部分：会议转写文本（最高优先级，生成纪要的主要依据）
    transcript_text = ctx['transcript'] if ctx['transcript'] else '无转写文本'
    user_msg = f"## 会议转写文本\n\n{transcript_text}\n\n"
    user_msg += "请根据以上所有信息，严格按照系统提示词的要求整理会议纪要。"
    user_msg += "注意：会议转写文本优先级最高，所有决策、变更、待办必须来源于此。"

    # 附加重新生成的原因和注意事项
    if regenerate_reason:
        user_msg += f"\n\n【重新生成原因】\n{regenerate_reason}"
    if regenerate_notes:
        user_msg += f"\n\n【注意事项】\n{regenerate_notes}"

    messages.append({"role": "user", "content": user_msg})

    # 如果有偏好模板，作为 assistant 参考示例
    if extra_context:
        messages.append({"role": "assistant", "content": extra_context})

    return messages