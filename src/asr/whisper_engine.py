"""
Faster-Whisper 引擎实现 (DESIGN.md §3.1.1)

基于 faster-whisper 库，本地离线语音转写。
支持 INT8 量化（CPU 推荐）和 FP16 推理（GPU）。
"""

import os
from pathlib import Path
from typing import Callable, Optional

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


def _apply_word_replace(text: str, replace_map: dict) -> str:
    """应用自定义词替换 + 用户更正记录"""
    if not replace_map:
        return text
    # 先应用用户累计的更正
    try:
        from src.storage.user_data import get_corrections
        user_map = get_corrections()
        for wrong, correct in user_map.items():
            text = text.replace(wrong, correct)
    except Exception:
        pass
    # 再应用 .env 配置的词替换
    result = text
    for wrong, correct in replace_map.items():
        result = result.replace(wrong, correct)
    return result


def _add_punctuation(segments: list) -> list:
    """
    根据段间停顿自动加标点。

    规则:
    - 段间间隔 > 2.0s → 上一段加句号，另起新段落
    - 段间间隔 > 0.8s → 上一段加句号
    - 段间间隔 > 0.3s → 上一段加逗号
    """
    if len(segments) < 2:
        if segments and segments[0].text and segments[0].text[-1] not in "。！？，、；：":
            segments[0].text += "。"
        return segments

    result = []
    for i, seg in enumerate(segments):
        text = seg.text
        if i < len(segments) - 1:
            gap = segments[i + 1].start - seg.end
            if gap > 2.0:
                text += "。\n\n"
            elif gap > 0.8:
                text += "。"
            elif gap > 0.3:
                text += "，"
        else:
            if text and text[-1] not in "。！？，、；：":
                text += "。"
        seg.text = text
        result.append(seg)
    return result


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

    def transcribe(self, audio_path: str, progress_callback: Optional[Callable[[float], None]] = None) -> ASRResult:
        """
        转写音频文件。

        Args:
            audio_path: 音频文件路径
            progress_callback: 进度回调，参数为 0.0~1.0 的进度值

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

        config = get_config()

        with LogTimer(logger, "ASR 转写"):
            try:
                segments_iter, info = self._model.transcribe(
                    audio_path,
                    beam_size=1,
                    language="zh",
                    vad_filter=True,  # 过滤静音段
                )
            except Exception as e:
                raise ASRError(f"Faster-Whisper 转写失败: {e}") from e

            # 收集所有片段并转简体 + 词替换
            replace_map = config.asr_word_replace_map
            segments = []
            full_text_parts = []
            total_duration = info.duration if hasattr(info, 'duration') and info.duration > 0 else 0.0
            for idx, seg in enumerate(segments_iter):
                text = _to_simplified(seg.text.strip())
                text = _apply_word_replace(text, replace_map)
                segments.append(ASRSegment(
                    start=seg.start,
                    end=seg.end,
                    text=text,
                ))
                full_text_parts.append(text)

                # 每 2 段回报一次进度（映射到 0.20 ~ 0.85 区间）
                if progress_callback and total_duration > 0 and idx % 2 == 0:
                    raw_pct = min(seg.end / total_duration, 1.0)
                    mapped = 0.20 + raw_pct * 0.65  # 0.20 → 0.85
                    progress_callback(mapped)

        # 加标点断句
        segments = _add_punctuation(segments)
        full_text = "".join(s.text for s in segments)
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