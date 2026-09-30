"""
重排序适配器 (Reranker)

统一接口：将检索结果按相关性重新排序，提升上下文质量。
当前实现：DashScope qwen3-rerank
"""

from abc import ABC, abstractmethod
from typing import Optional

import httpx

from src.log_utils import get_logger

logger = get_logger(__name__)


class Reranker(ABC):
    """重排序适配器抽象基类"""

    @abstractmethod
    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_n: Optional[int] = None,
    ) -> list[dict]:
        """
        对候选文档块进行重排序。

        Args:
            query: 查询文本（会议背景 + 转写摘要）
            candidates: [{"text": "...", "score": 0.0, "meta": {...}}, ...]
            top_n: 返回 top-N 条结果（默认全部）

        Returns:
            [{"text": "...", "relevance_score": 0.95, "meta": {...}}, ...]
            按相关性降序排列
        """
        ...

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """测试连接，返回 (成功, 错误信息)"""
        ...


class DashScopeReranker(Reranker):
    """DashScope qwen3-rerank 实现（也支持 OpenAI 兼容模式）"""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-rerank",
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

    async def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_n: Optional[int] = None,
    ) -> list[dict]:
        if not candidates or not self.api_key:
            logger.warning("Reranker: 无候选项或未配置 API Key")
            return candidates

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self._is_openai:
            # OpenAI 兼容格式 — 直接按得分降序取 top_n
            scored = []
            for c in candidates:
                scored.append({
                    "text": c["text"],
                    "relevance_score": c.get("score", 0),
                    "meta": c.get("meta", {}),
                })
            scored.sort(key=lambda x: x["relevance_score"], reverse=True)
            result = scored[:top_n] if top_n else scored
            logger.debug("Rerank (OpenAI mode) %d candidates → %d results", len(candidates), len(result))
            return result
        else:
            # DashScope 原生格式
            url = f"{self.base_url}/services/rerank/text-rerank/text-rerank"
            documents = [c["text"] for c in candidates]
            payload = {
                "model": self.model,
                "input": {
                    "query": query,
                    "documents": documents,
                },
            }
            if top_n:
                payload["parameters"] = {"top_n": top_n}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                try:
                    resp = await client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("output", {}).get("results", [])

                    reranked = []
                    for r in results:
                        idx = r.get("index", 0)
                        if idx < len(candidates):
                            reranked.append({
                                "text": candidates[idx]["text"],
                                "relevance_score": r.get("relevance_score", 0),
                                "meta": candidates[idx].get("meta", {}),
                            })

                    logger.debug("Rerank %d candidates → %d results", len(candidates), len(reranked))
                    return reranked
                except Exception as e:
                    logger.error("Reranker 请求失败: %s", e)
                    raise

    async def test_connection(self) -> tuple[bool, str]:
        """测试连接，返回 (成功, 错误信息)"""
        try:
            await self.rerank("test", [{"text": "test"}], top_n=1)
            return True, ""
        except httpx.HTTPStatusError as e:
            detail = e.response.text[:200] if e.response else str(e)
            logger.error("Reranker 连接测试失败: %s", detail)
            return False, f"HTTP {e.response.status_code}: {detail}"
        except httpx.RequestError as e:
            logger.error("Reranker 网络错误: %s", e)
            return False, f"网络错误: {e}"
        except Exception as e:
            logger.error("Reranker 连接测试失败: %s", e)
            return False, str(e)


def get_reranker() -> Optional[Reranker]:
    """获取 Reranker 实例（根据配置自动选择）"""
    from src.config import get_config
    config = get_config()

    api_key = config.RERANK_API_KEY or config.DASHSCOPE_API_KEY
    if not api_key:
        logger.warning("未配置 Reranker API Key，重排序功能不可用")
        return None

    provider = config.RERANK_PROVIDER
    if provider in ("dashscope", "custom", "openai"):
        return DashScopeReranker(
            api_key=api_key,
            model=config.RERANK_MODEL,
            base_url=config.RERANK_BASE_URL,
            provider=provider,
        )

    logger.warning("不支持的 Reranker 提供商: %s", provider)
    return None