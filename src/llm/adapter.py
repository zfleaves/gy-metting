"""
LLM 适配器抽象层 (DESIGN.md §3.3.1)

定义统一的 LLM 调用接口，支持流式输出。
模型无关，通过配置切换不同提供商。
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class LLMAdapter(ABC):
    """LLM 适配器抽象基类"""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> AsyncGenerator[str, None]:
        """
        统一聊天接口。

        Args:
            messages: OpenAI 格式消息列表 [{"role": "system"|"user"|"assistant", "content": "..."}]
            temperature: 温度参数 (0.0 ~ 2.0)
            max_tokens: 最大输出 token 数
            stream: 是否流式输出

        Yields:
            stream=False: 单次 yield 完整响应文本
            stream=True: 逐 block yield 文本片段
        """
        ...

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """估算 token 数量（用于上下文截断判断）"""
        ...


def get_llm_adapter() -> LLMAdapter:
    """根据配置获取 LLM 适配器实例"""
    from src.config import get_config
    config = get_config()

    provider = config.LLM_PROVIDER
    base_url = config.LLM_BASE_URL
    api_key = config.LLM_API_KEY
    model = config.LLM_MODEL

    # 优先从 LLM 来源管理获取激活的配置
    from src.storage.db import SessionLocal
    from src.storage.models import LlmSource
    db = SessionLocal()
    try:
        active = (
            db.query(LlmSource)
            .filter(LlmSource.is_active == "1")
            .order_by(LlmSource.created_at.desc())
            .first()
        )
        if active:
            provider = active.provider
            base_url = active.base_url
            api_key = active.api_key
            model = active.model
    finally:
        db.close()

    from src.llm.openai_compat import OpenAICompatAdapter
    return OpenAICompatAdapter(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )