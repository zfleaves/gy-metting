"""
Embedding 适配器 (DESIGN.md §3.3.1 扩展)

统一文本嵌入接口，支持多种嵌入模型提供商。
当前实现：DashScope text-embedding-v4
"""

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from src.log_utils import get_logger

logger = get_logger(__name__)


class EmbeddingAdapter(ABC):
    """Embedding 适配器抽象基类"""

    @abstractmethod
    async def embed(self, texts: list[str], text_type: str = "document") -> list[list[float]]:
        """批量文本 → 向量列表"""
        ...

    @abstractmethod
    async def embed_query(self, text: str) -> list[float]:
        """单条查询文本 → 向量"""
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """测试连接是否正常，返回 (成功, 错误信息)"""
        ...


class DashScopeEmbedding(EmbeddingAdapter):
    """DashScope text-embedding-v4 实现（也支持 OpenAI 兼容模式）"""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-v4",
        base_url: str = "https://dashscope.aliyuncs.com/api/v1",
        provider: str = "dashscope",
        timeout: int = 60,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.provider = provider
        self.timeout = timeout
        self._is_openai = provider.lower() in ("custom", "openai")

    def _get_url_and_payload(self, texts: list[str], text_type: str = "document"):
        """根据 provider 返回 (url, payload)"""
        if self._is_openai:
            # OpenAI 兼容格式
            url = f"{self.base_url}/embeddings"
            payload = {
                "model": self.model,
                "input": texts if len(texts) > 1 else texts[0],
            }
        else:
            # DashScope 原生格式
            url = f"{self.base_url}/services/embeddings/text-embedding/text-embedding"
            payload = {
                "model": self.model,
                "input": {"texts": texts},
                "parameters": {"text_type": text_type},
            }
        return url, payload

    async def embed(self, texts: list[str], text_type: str = "document") -> list[list[float]]:
        """批量文本嵌入"""
        if not texts or not self.api_key:
            logger.warning("Embedding: 无文本或未配置 API Key")
            return []

        url, payload = self._get_url_and_payload(texts, text_type)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()

                if self._is_openai:
                    # OpenAI 格式: data[{index, embedding, object}]
                    items = data.get("data", [])
                    sorted_items = sorted(items, key=lambda x: x.get("index", 0))
                    result = [item["embedding"] for item in sorted_items]
                else:
                    # DashScope 格式: output.embeddings[{text_index, embedding}]
                    embeddings = data.get("output", {}).get("embeddings", [])
                    sorted_emb = sorted(embeddings, key=lambda x: x.get("text_index", 0))
                    result = [e["embedding"] for e in sorted_emb]

                logger.debug("Embedding %d texts, dim=%d", len(result), len(result[0]) if result else 0)
                return result
            except Exception as e:
                logger.error("Embedding 请求失败: %s", e)
                raise

    async def embed_query(self, text: str) -> list[float]:
        """查询文本嵌入 (text_type=query)"""
        results = await self.embed([text], text_type="query")
        return results[0] if results else []

    async def test_connection(self) -> tuple[bool, str]:
        """测试连接，返回 (成功, 错误信息)"""
        try:
            await self.embed(["test"], text_type="document")
            return True, ""
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:200] if e.response else str(e)
            logger.error("Embedding 连接测试失败: %s", detail)
            return False, f"HTTP {e.response.status_code}: {detail}"
        except httpx.RequestError as e:
            logger.error("Embedding 网络错误: %s", e)
            return False, f"网络错误: {e}"
        except Exception as e:
            logger.error("Embedding 连接测试失败: %s", e)
            return False, str(e)


def get_embedding_adapter() -> Optional[EmbeddingAdapter]:
    """获取 Embedding 适配器实例（根据配置自动选择）"""
    from src.config import get_config
    config = get_config()

    api_key = config.EMBEDDING_API_KEY or config.DASHSCOPE_API_KEY
    if not api_key:
        logger.warning("未配置 Embedding API Key，RAG 功能不可用")
        return None

    provider = config.EMBEDDING_PROVIDER
    if provider in ("dashscope", "custom", "openai"):
        return DashScopeEmbedding(
            api_key=api_key,
            model=config.EMBEDDING_MODEL,
            base_url=config.EMBEDDING_BASE_URL,
            provider=provider,
        )

    logger.warning("不支持的 Embedding 提供商: %s", provider)
    return None