"""
ASR 任务处理器 (DESIGN.md §3.1.1 + §3.6)

连接任务队列与 ASR 引擎，将转写结果保存到文件。
"""

import os
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
    处理 ASR 转写任务。

    Args:
        task_id: 任务 ID
        params: {"audio_path": "..."}

    Returns:
        {"result_path": "...", "text_preview": "...", "segments_count": N}
    """
    audio_path = params.get("audio_path")
    if not audio_path:
        raise ValueError("缺少 audio_path 参数")

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"音频文件不存在: {audio_path}")

    engine = _get_engine()
    result = engine.transcribe(audio_path)

    # 保存转写结果到文件
    config = get_config()
    output_dir = config.resolve_path(config.OUTPUT_DIR) / "transcripts"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 保存完整文本
    txt_path = output_dir / f"{task_id}.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(result.text)
        f.write("\n\n--- 分段 ---\n\n")
        for seg in result.segments:
            f.write(f"[{seg.start:.1f}s - {seg.end:.1f}s] {seg.text}\n")

    logger.info("ASR 结果已保存: %s (%d 字)", txt_path, len(result.text))

    return {
        "result_path": str(txt_path),
        "text_preview": result.text[:500],
        "segments_count": len(result.segments),
        "language": result.language,
        "duration_seconds": result.duration_seconds,
        "engine": result.engine,
    }


def register_asr_handler() -> None:
    """将 ASR 处理器注册到任务管理器"""
    from src.task.queue import get_task_manager
    manager = get_task_manager()
    manager.register_handler(TaskType.ASR, handle_asr_task)
    logger.info("ASR 任务处理器已注册")