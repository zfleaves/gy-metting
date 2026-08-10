"""
Faster-Whisper 引擎实现 (DESIGN.md §3.1.1)

基于 faster-whisper 库，本地离线语音转写。
支持 INT8 量化（CPU 推荐）和 FP16 推理（GPU）。
"""

import os
from pathlib import Path
from typing import Optional

from src.asr.base import ASRError, ASRResult, ASRSegment, BaseASREngine
from src.config import get_config
from src.log_utils import get_logger, LogTimer

logger = get_logger(__name__)


def _to_simplified(text: str) -> str:
    """繁体转简体"""
    try:
        from zhconv import convert
        return convert(text, "zh-cn")
    except ImportError:
        return text


class WhisperEngine(BaseASREngine):
    """Faster-Whisper 引擎"""

    def __init__(
        self,
        model_size: Optional[str] = None,
        compute_type: Optional[str] = None,
        device: Optional[str] = None,
    ):
        config = get_config()
        self.model_size = model_size or config.WHISPER_MODEL_SIZE
        self.compute_type = compute_type or config.WHISPER_COMPUTE_TYPE
        self.device = device or config.WHISPER_DEVICE
        self._model = None

    @property
    def name(self) -> str:
        return f"faster-whisper ({self.model_size}, {self.compute_type})"

    def load_model(self) -> None:
        """加载 Whisper 模型"""
        if self._model is not None:
            return

        logger.info("加载 Faster-Whisper 模型: size=%s, compute=%s, device=%s",
                     self.model_size, self.compute_type, self.device)

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ASRError(
                "faster-whisper 未安装，请运行: pip install faster-whisper"
            )

        with LogTimer(logger, "Faster-Whisper 模型加载"):
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )

        logger.info("Faster-Whisper 模型加载完成")

    def transcribe(self, audio_path: str) -> ASRResult:
        """
        转写音频文件。

        Args:
            audio_path: 音频文件路径

        Returns:
            ASRResult: 转写结果

        Raises:
            FileNotFoundError: 音频文件不存在
            ASRError: 转写失败
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"音频文件不存在: {audio_path}")

        if self._model is None:
            self.load_model()

        logger.info("开始转写: %s", audio_path)
        file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
        logger.info("音频大小: %.1f MB", file_size_mb)

        with LogTimer(logger, "ASR 转写"):
            try:
                segments_iter, info = self._model.transcribe(
                    audio_path,
                    beam_size=5,
                    language="zh",
                    vad_filter=True,  # 过滤静音段
                )
            except Exception as e:
                raise ASRError(f"Faster-Whisper 转写失败: {e}") from e

            # 收集所有片段并转简体
            segments = []
            full_text_parts = []
            for seg in segments_iter:
                text = _to_simplified(seg.text.strip())
                segments.append(ASRSegment(
                    start=seg.start,
                    end=seg.end,
                    text=text,
                ))
                full_text_parts.append(text)

        full_text = " ".join(full_text_parts)
        duration = info.duration if hasattr(info, 'duration') else 0.0
        language = info.language if hasattr(info, 'language') else "zh"

        logger.info(
            "转写完成: %d 片段, 语言=%s, 音频时长=%.1fs, 文本长度=%d",
            len(segments), language, duration, len(full_text),
        )

        return ASRResult(
            text=full_text,
            segments=segments,
            language=language,
            duration_seconds=duration,
            engine=self.name,
        )