"""
ASR 语音转写模块 (DESIGN.md §3.1.1)

主选：Faster-Whisper（本地离线）
备选：Qwen3-ASR-Flash（云端 API）

工厂函数:
    create_asr_engine() → BaseASREngine
"""

from src.asr.base import ASRError, ASRResult, ASRSegment, BaseASREngine
from src.config import get_config


def create_asr_engine() -> BaseASREngine:
    """
    根据配置创建 ASR 引擎实例。

    Returns:
        BaseASREngine: 配置对应的引擎实例

    Raises:
        ValueError: 不支持的 ASR 引擎
    """
    config = get_config()
    engine_name = config.ASR_ENGINE.lower()

    if engine_name == "faster_whisper":
        from src.asr.whisper_engine import WhisperEngine
        return WhisperEngine(
            model_size=config.WHISPER_MODEL_SIZE,
            compute_type=config.WHISPER_COMPUTE_TYPE,
            device=config.WHISPER_DEVICE,
        )
    elif engine_name == "qwen3_asr_flash":
        # TODO: Qwen3-ASR-Flash 备选引擎（M2+）
        raise NotImplementedError("Qwen3-ASR-Flash 引擎尚未实现")
    else:
        raise ValueError(f"不支持的 ASR 引擎: {engine_name}")


__all__ = [
    "create_asr_engine",
    "BaseASREngine",
    "ASRResult",
    "ASRSegment",
    "ASRError",
]