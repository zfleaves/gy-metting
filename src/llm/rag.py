"""
RAG 引擎 (DESIGN.md §3.3.2 扩展)

编排 Embedding + 检索 + 重排序，将参考文档中最相关的内容提取到上下文中。
"""

import math
from typing import Optional

from src.log_utils import get_logger
from src.llm.chunker import DocumentChunker

logger = get_logger(__name__)


class RagEngine:
    """RAG 检索增强引擎"""

    def __init__(
        self,
        embedding: Optional["EmbeddingAdapter"] = None,  # noqa: F821
        reranker: Optional["Reranker"] = None,  # noqa: F821
        chunker: Optional[DocumentChunker] = None,
        top_k: int = 10,
        rerank_top_n: int = 5,
    ):
        """
        Args:
            embedding: Embedding 适配器（None 则降级为暴力截断）
            reranker: Reranker 适配器（None 则跳过重排序）
            chunker: 文档分块器
            top_k: 检索 top-K
            rerank_top_n: 重排后取 top-N
        """
        self.embedding = embedding
        self.reranker = reranker
        self.chunker = chunker or DocumentChunker()
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n

    async def prepare_context(self, query: str, documents: list[dict]) -> str:
        """
        RAG 流水线：分块 → Embedding → 检索 → 重排序 → 上下文文本

        Args:
            query: 查询文本（会议背景 + 转写摘要）
            documents: [{"title": "...", "content": "..."}, ...]

        Returns:
            格式化上下文文本（最相关的文档块）
        """
        if not documents:
            return ""

        # 降级：无 embedding 模型时直接返回原始截断
        if not self.embedding:
            logger.info("RAG: 无 Embedding 模型，使用暴力截断")
            return self._fallback_truncate(documents)

        # 1. 分块
        chunks = self.chunker.chunk(documents)
        if not chunks:
            return ""
        logger.info("RAG: %d 文档 → %d 块", len(documents), len(chunks))

        # 2. Embedding（批量）
        chunk_texts = [c.text for c in chunks]
        try:
            vectors = await self.embedding.embed(chunk_texts)
        except Exception as e:
            logger.error("RAG Embedding 失败: %s，降级为暴力截断", e)
            return self._fallback_truncate(documents)

        if not vectors:
            return self._fallback_truncate(documents)

        # 3. 查询向量
        try:
            query_vector = await self.embedding.embed_query(query)
        except Exception:
            query_vector = vectors[0] if vectors else []

        if not query_vector:
            return self._fallback_truncate(documents)

        # 4. 余弦相似度检索 top-K
        scored = self._cosine_similarity(query_vector, vectors, chunks)

        # 5. 重排序（可选）
        if self.reranker and scored:
            candidates = [
                {
                    "text": s["text"],
                    "meta": {"doc_title": s["doc_title"], "heading": s["heading"]},
                }
                for s in scored
            ]
            try:
                reranked = await self.reranker.rerank(query, candidates, top_n=self.rerank_top_n)
            except Exception as e:
                logger.warning("Reranker 失败: %s，跳过重排序", e)
                reranked = scored[:self.rerank_top_n]

            selected = reranked
        else:
            selected = scored[:self.rerank_top_n]

        logger.info("RAG: 选中 %d 个相关块参与生成", len(selected))

        # 6. 组装上下文
        return self._assemble_context(selected)

    def _cosine_similarity(
        self,
        query_vec: list[float],
        doc_vectors: list[list[float]],
        chunks: list,
    ) -> list[dict]:
        """余弦相似度检索"""
        scored = []
        for i, vec in enumerate(doc_vectors):
            if i >= len(chunks):
                break
            score = self._cosine(query_vec, vec)
            scored.append({
                "text": chunks[i].text,
                "score": score,
                "doc_title": chunks[i].doc_title,
                "heading": chunks[i].heading,
            })
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:self.top_k]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        """余弦相似度"""
        if not a or not b or len(a) != len(b):
            return 0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _assemble_context(selected: list[dict]) -> str:
        """组装选中块为格式化文本"""
        blocks = []
        for i, item in enumerate(selected):
            source = ""
            if item.get("doc_title"):
                source += f"📄 {item['doc_title']}"
            if item.get("heading"):
                source += f" → {item['heading']}"
            score = item.get("relevance_score", item.get("score", 0))
            if score:
                source += f" (相关度: {score:.2f})"

            block = source + "\n\n" + item["text"] if source else item["text"]
            blocks.append(block)

        return "\n\n---\n\n".join(blocks)

    @staticmethod
    def _fallback_truncate(documents: list[dict]) -> str:
        """降级：原始暴力截断"""
        blocks = []
        for d in documents:
            content = d.get("content", "")
            if len(content) > 5000:
                content = content[:5000] + f"\n\n...（文档过长，已截断）"
            blocks.append(f"### {d.get('title', '')}\n\n{content}")
        return "\n\n---\n\n".join(blocks)


async def get_rag_context(query: str, documents: list[dict]) -> str:
    """
    快捷函数：获取 RAG 增强后的上下文。

    自动根据配置初始化引擎，配置不可用时自动降级。
    """
    from src.config import get_config
    config = get_config()

    if not config.RAG_ENABLED:
        # RAG 未启用，直接降级
        return RagEngine._fallback_truncate(documents)

    from src.llm.embedding import get_embedding_adapter
    from src.llm.reranker import get_reranker
    from src.llm.chunker import DocumentChunker

    embedding = get_embedding_adapter()
    reranker = get_reranker()
    chunker = DocumentChunker(
        chunk_size=config.RAG_CHUNK_SIZE,
        overlap=config.RAG_CHUNK_OVERLAP,
    )

    engine = RagEngine(
        embedding=embedding,
        reranker=reranker,
        chunker=chunker,
        top_k=config.RAG_TOP_K,
        rerank_top_n=config.RAG_RERANK_TOP_N,
    )

    return await engine.prepare_context(query, documents)