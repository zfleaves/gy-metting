"""
ASR 任务处理器 (DESIGN.md §3.1.1 + §3.6)

连接任务队列与 ASR 引擎，将转写结果保存到文件。
所有重 CPU 操作（模型加载、转写）通过线程池执行，避免阻塞事件循环。
"""

import asyncio
import json
import os
import time
from typing import Any, Dict

from src.asr import create_asr_engine
from src.config import get_config
from src.log_utils import get_logger
from src.storage.models import TaskType

logger = get_logger(__name__)

# 引擎实例（延迟加载，单例）
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_asr_engine()
        _engine.load_model()
    return _engine


async def handle_asr_task(task_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 ASR 转写任务。支持单个或多个音频文件合并转写。
    重 CPU 部分通过线程池执行。
    """
    audio_paths = params.get("audio_paths") or (
        [params["audio_path"]] if params.get("audio_path") else None
    )
    if not audio_paths:
        raise ValueError("缺少 audio_path 或 audio_paths 参数")

    for p in audio_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(f"音频文件不存在: {p}")

    # 更新进度：加载模型
    _update_progress(task_id, 0.05)

    # 模型加载 → 线程池
    engine = await asyncio.to_thread(_get_engine)

    all_segments = []
    full_text_parts = []
    total_duration = 0.0
    time_offset = 0.0
    file_count = len(audio_paths)
    is_merged = file_count > 1

    for idx, audio_path in enumerate(audio_paths):
        # 更新进度：开始转写当前文件
        progress_start = 0.1 + (idx / file_count) * 0.7
        _update_progress(task_id, progress_start)

        # 节流进度回调
        _throttle_state = {"last_db_write": 0.0}

        def _on_progress(p: float) -> None:
            now = time.time()
            if now - _throttle_state["last_db_write"] >= 2.0:
                # 将单文件进度映射到整体进度区间
                mapped = progress_start + (p * 0.7 / file_count)
                _update_progress(task_id, round(mapped, 2))
                _throttle_state["last_db_write"] = now

        logger.info("ASR 转写 [%d/%d]: %s", idx + 1, file_count, audio_path)

        # 转写 → 线程池
        result = await asyncio.to_thread(
            engine.transcribe, audio_path, progress_callback=_on_progress
        )

        # 合并 segments（时间戳累加）
        for seg in result.segments:
            all_segments.append({
                "start": round(seg.start + time_offset, 1),
                "end": round(seg.end + time_offset, 1),
                "text": seg.text,
                "file_index": idx,
            })

        full_text_parts.append(result.text)
        total_duration += result.duration_seconds
        time_offset = total_duration

    # 更新进度：保存结果
    _update_progress(task_id, 0.9)

    # 保存转写结果到文件
    config = get_config()
    output_dir = config.resolve_path(config.OUTPUT_DIR) / "transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 合并文本
    merged_text = "\n\n".join(full_text_parts)

    # 保存纯文本
    txt_path = output_dir / f"{task_id}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(merged_text)
        f.write("\n\n--- 分段 ---\n\n")
        for seg in all_segments:
            file_label = f"[文件{seg['file_index'] + 1}] " if is_merged else ""
            f.write(f"{file_label}[{seg['start']:.1f}s - {seg['end']:.1f}s] {seg['text']}\n")

    # 保存分段 JSON（前端用）
    json_path = output_dir / f"{task_id}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_segments, f, ensure_ascii=False, indent=2)

    # 自动标记重点（关键词匹配）
    auto_highlighted = _auto_highlight(all_segments, config.auto_highlight_keywords)
    highlights_path = output_dir / f"{task_id}_highlights.json"
    with open(highlights_path, "w", encoding="utf-8") as f:
        json.dump({"highlighted_indices": auto_highlighted}, f, ensure_ascii=False)

    logger.info("ASR 结果已保存: %s (%d 字, %d 段, %d 重点, %d 个文件)",
                txt_path, len(merged_text), len(all_segments), len(auto_highlighted), file_count)

    return {
        "result_path": str(txt_path),
        "segments_path": str(json_path),
        "audio_path": audio_paths[0] if not is_merged else audio_paths[0],
        "text_preview": merged_text[:500],
        "segments_count": len(all_segments),
        "language": result.language,
        "duration_seconds": total_duration,
        "engine": result.engine,
        "merged": is_merged,
        "file_count": file_count,
    }


def _auto_highlight(segments: list, keywords: list) -> list:
    """根据关键词自动标记重点语句，返回高亮索引列表"""
    if not keywords:
        return []
    highlighted = []
    for i, seg in enumerate(segments):
        for kw in keywords:
            if kw in seg["text"]:
                highlighted.append(i)
                break
    return highlighted


def _update_progress(task_id: str, progress: float) -> None:
    """更新任务进度到数据库"""
    try:
        from src.storage.db import SessionLocal
        from src.storage.models import Task
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if task:
                task.progress = progress
                db.commit()
        finally:
            db.close()
    except Exception:
        pass  # 进度更新失败不影响主流程


def register_asr_handler() -> None:
    """将 ASR 处理器注册到任务管理器"""
    from src.task.queue import get_task_manager
    manager = get_task_manager()
    manager.register_handler(TaskType.ASR, handle_asr_task)
    logger.info("ASR 任务处理器已注册")