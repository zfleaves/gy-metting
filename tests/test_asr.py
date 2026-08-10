"""测试 ASR 模块"""

import pytest
from src.asr.base import ASRError, ASRResult, ASRSegment, BaseASREngine
from src.asr import create_asr_engine


class TestASRBase:
    """ASR 抽象层测试"""

    def test_asr_result_defaults(self):
        """ASRResult 默认值"""
        result = ASRResult(text="测试文本")
        assert result.text == "测试文本"
        assert result.segments == []
        assert result.language == "zh"
        assert result.duration_seconds == 0.0

    def test_asr_segment(self):
        """ASRSegment 数据类"""
        seg = ASRSegment(start=0.0, end=2.5, text="你好")
        assert seg.start == 0.0
        assert seg.end == 2.5
        assert seg.text == "你好"

    def test_asr_error(self):
        """ASRError 异常"""
        with pytest.raises(ASRError):
            raise ASRError("测试错误")

    def test_create_engine(self):
        """工厂函数创建引擎"""
        engine = create_asr_engine()
        assert isinstance(engine, BaseASREngine)
        assert "faster-whisper" in engine.name

    def test_abstract_base(self):
        """抽象基类不能直接实例化"""
        with pytest.raises(TypeError):
            BaseASREngine()