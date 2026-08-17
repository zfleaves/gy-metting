"""
ASR 引擎抽象层 (DESIGN.md §3.1.1)

定义统一的语音转写接口，支持：
- Faster-Whisper（主选，本地离线）
- Qwen3-ASR-Flash（备选，云端 API）
"""

import abc
from dataclasses import dataclass, field
from typing import Callable, List, Optional


@dataclass
class ASRSegment:
    """转写片段"""
    start: float        # 开始时间（秒）
    end: float          # 结束时间（秒）
    text: str           # 文本内容


@dataclass
class ASRResult:
    """转写结果"""
    text: str                           # 完整文本
    segments: List[ASRSegment] = field(default_factory=list)
    language: str = "zh"                # 检测到的语言
    duration_seconds: float = 0.0       # 音频时长
    engine: str = ""                    # 使用的引擎名称


class BaseASREngine(abc.ABC):
    """ASR 引擎抽象基类"""

    @abc.abstractmethod
    def transcribe(self, audio_path: str, progress_callback: Optional[Callable[[float], None]] = None) -> ASRResult:
        """
        转写音频文件为文本。

        Args:
            audio_path: 音频文件路径（mp3/wav/m4a）
            progress_callback: 进度回调，参数为 0.0~1.0 的进度值

        Returns:
            ASRResult: 包含完整文本和分段时间戳

        Raises:
            FileNotFoundError: 音频文件不存在
            ASRError: 转写失败
        """
        ...

    @abc.abstractmethod
    def load_model(self) -> None:
        """加载/预热模型（耗时操作，启动时调用）"""
        ...

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """引擎名称"""
        ...


class ASRError(Exception):
    """ASR 转写异常"""
    pass