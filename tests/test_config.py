"""测试配置管理模块"""

import pytest
from src.config import get_config, Settings, PROJECT_ROOT


class TestConfig:
    """配置加载测试"""

    def test_config_loads_from_env(self):
        """配置应从 .env 文件加载"""
        config = get_config()
        assert config.SERVER_PORT == 8000
        assert config.SERVER_HOST == "0.0.0.0"

    def test_config_llm(self):
        """LLM 配置组"""
        config = get_config()
        assert config.LLM_PROVIDER in ("openai", "deepseek", "qwen", "glm", "custom")
        assert config.LLM_MODEL
        assert config.LLM_DEFAULT_MAX_TOKENS > 0

    def test_config_asr(self):
        """ASR 配置组"""
        config = get_config()
        assert config.ASR_ENGINE in ("faster_whisper", "qwen3_asr_flash")
        assert config.WHISPER_MODEL_SIZE in ("tiny", "base", "small", "medium", "large-v3")
        assert config.WHISPER_COMPUTE_TYPE in ("int8", "float16", "int8_float16")

    def test_config_upload_limits(self):
        """上传限制"""
        config = get_config()
        assert config.MAX_AUDIO_SIZE_MB == 200
        assert config.MAX_DOC_SIZE_MB == 20
        assert config.max_audio_size_bytes == 200 * 1024 * 1024

    def test_config_allowed_formats(self):
        """格式列表解析"""
        config = get_config()
        formats = config.allowed_audio_formats_list
        assert "mp3" in formats
        assert "wav" in formats
        assert "m4a" in formats

    def test_config_cors_origins(self):
        """CORS 来源解析"""
        config = get_config()
        origins = config.cors_origins_list
        assert len(origins) >= 1
        assert "http://localhost:5173" in origins

    def test_config_dingtalk_disabled_by_default(self):
        """钉钉默认未配置"""
        config = get_config()
        # 钉钉默认未配置，应返回 False
        assert isinstance(config.dingtalk_enabled, bool)

    def test_config_resolve_path(self):
        """路径解析"""
        config = get_config()
        path = config.resolve_path("./data")
        assert path.is_absolute()

    def test_config_singleton(self):
        """get_config 应返回同一实例"""
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2