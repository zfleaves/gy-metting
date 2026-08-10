"""
配置管理模块 (DESIGN.md §7.1 + §7.2 + §9)

从 .env 文件加载所有配置，使用 pydantic-settings 进行校验。
所有配置集中管理，业务代码通过 `get_config()` 获取。
"""

import os
from pathlib import Path
from functools import lru_cache
from typing import Optional, List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# 项目根目录（gy-meeting/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """应用配置，从 .env 加载，字段名对应环境变量"""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ============================================================
    # 1. 服务基础配置
    # ============================================================
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # ============================================================
    # 2. LLM 大模型配置
    # ============================================================
    LLM_PROVIDER: str = "openai"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o"
    LLM_DEFAULT_TEMPERATURE: float = 0.3
    LLM_DEFAULT_MAX_TOKENS: int = 4096
    LLM_TIMEOUT_SECONDS: int = 120
    LLM_MAX_RETRIES: int = 3

    # 备用模型
    LLM_PROVIDER_ALT: Optional[str] = None
    LLM_BASE_URL_ALT: Optional[str] = None
    LLM_API_KEY_ALT: Optional[str] = None
    LLM_MODEL_ALT: Optional[str] = None

    # ============================================================
    # 3. ASR 语音转写配置
    # ============================================================
    ASR_ENGINE: str = "faster_whisper"
    WHISPER_MODEL_SIZE: str = "small"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_DEVICE: str = "auto"
    ASR_WORD_REPLACE: str = ""  # 自定义词替换: 错词=正确词,错词2=正确词2
    ASR_AUTO_HIGHLIGHT: str = ""  # 自动标记重点关键词: 词1,词2,词3
    DASHSCOPE_API_KEY: Optional[str] = None

    # ============================================================
    # 4. 语雀文档拉取配置
    # ============================================================
    YUQUE_KNOWLEDGE_BASE_URL: Optional[str] = None
    YUQUE_API_TOKEN: Optional[str] = None
    YUQUE_API_BASE_URL: str = "https://www.yuque.com/api/v2"
    YUQUE_TIMEOUT_SECONDS: int = 30
    YUQUE_SESSION: Optional[str] = None
    YUQUE_CTOKEN: Optional[str] = None

    # ============================================================
    # 5. 钉钉机器人推送配置
    # ============================================================
    DINGTALK_WEBHOOK_URL: Optional[str] = None
    DINGTALK_WEBHOOK_SECRET: Optional[str] = None

    # ============================================================
    # 6. 数据库配置
    # ============================================================
    DATABASE_URL: str = "sqlite:///data/meeting.db"
    SQLITE_WAL_MODE: bool = True

    # ============================================================
    # 7. 文件存储路径
    # ============================================================
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"
    SNAPSHOT_DIR: str = "./data/snapshots"
    OUTPUT_DIR: str = "./data/outputs"
    TEMP_DIR: str = "./data/temp"

    # ============================================================
    # 8. 上传限制
    # ============================================================
    MAX_AUDIO_SIZE_MB: int = 200
    MAX_DOC_SIZE_MB: int = 20
    ALLOWED_AUDIO_FORMATS: str = "mp3,wav,m4a"
    ALLOWED_DOC_FORMATS: str = "docx,pdf,txt,md"

    # ============================================================
    # 9. 任务队列配置
    # ============================================================
    TASK_TIMEOUT_MINUTES: int = 30
    SYNC_THRESHOLD_MINUTES: int = 30
    MAX_CONCURRENT_TASKS: int = 1

    # ============================================================
    # 10. 安全配置
    # ============================================================
    SECRET_KEY: str = "change-me-to-a-random-secret-key"
    CORS_ORIGINS: str = "http://localhost:5173"

    # ============================================================
    # 辅助方法
    # ============================================================

    @property
    def cors_origins_list(self) -> List[str]:
        """解析 CORS 来源列表"""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_audio_formats_list(self) -> List[str]:
        return [f.strip().lower() for f in self.ALLOWED_AUDIO_FORMATS.split(",")]

    @property
    def allowed_doc_formats_list(self) -> List[str]:
        return [f.strip().lower() for f in self.ALLOWED_DOC_FORMATS.split(",")]

    @property
    def max_audio_size_bytes(self) -> int:
        return self.MAX_AUDIO_SIZE_MB * 1024 * 1024

    @property
    def max_doc_size_bytes(self) -> int:
        return self.MAX_DOC_SIZE_MB * 1024 * 1024

    @property
    def dingtalk_enabled(self) -> bool:
        """钉钉推送是否已配置"""
        return bool(self.DINGTALK_WEBHOOK_URL and self.DINGTALK_WEBHOOK_URL.strip())

    @property
    def yuque_enabled(self) -> bool:
        """语雀拉取是否已配置"""
        return bool(self.YUQUE_API_TOKEN and self.YUQUE_API_TOKEN.strip())

    @property
    def asr_word_replace_map(self) -> dict:
        """解析自定义词替换映射"""
        if not self.ASR_WORD_REPLACE.strip():
            return {}
        result = {}
        for pair in self.ASR_WORD_REPLACE.split(","):
            pair = pair.strip()
            if "=" in pair:
                k, v = pair.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    @property
    def auto_highlight_keywords(self) -> list:
        """解析自动标记关键词列表"""
        if not self.ASR_AUTO_HIGHLIGHT.strip():
            return []
        return [k.strip() for k in self.ASR_AUTO_HIGHLIGHT.split(",") if k.strip()]

    def resolve_path(self, relative_path: str) -> Path:
        """将相对路径解析为绝对路径（相对于项目根目录）"""
        p = Path(relative_path)
        if p.is_absolute():
            return p
        return (PROJECT_ROOT / p).resolve()


@lru_cache()
def get_config() -> Settings:
    """获取配置单例（带缓存）"""
    return Settings()


# 便捷导出
config = get_config()