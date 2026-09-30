"""
文档分块引擎 (DESIGN.md §3.3.2 扩展)

将参考文档按标题/段落切割为语义块，保留结构化元信息。
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.log_utils import get_logger

logger = get_logger(__name__)


@dataclass
class Chunk:
    """文档块"""
    doc_title: str = ""          # 所属文档标题
    heading: str = ""            # 当前小节标题
    heading_level: int = 0       # 标题层级 (0=无标题, 1=#, 2=##, 3=###)
    text: str = ""               # 块文本内容
    position: int = 0            # 在文档中的位置序号
    token_estimate: int = 0      # 估算 token 数


class DocumentChunker:
    """文档分块器"""

    def __init__(self, chunk_size: int = 512, overlap: int = 64):
        """
        Args:
            chunk_size: 每块目标 token 数
            overlap: 相邻块重叠 token 数
        """
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk(self, documents: list[dict]) -> list[Chunk]:
        """
        将文档列表分割为块。

        Args:
            documents: [{"title": "文档名", "content": "markdown 文本"}, ...]

        Returns:
            [Chunk, ...]
        """
        all_chunks: list[Chunk] = []
        pos = 0

        for doc in documents:
            title = doc.get("title", "")
            content = doc.get("content", "")
            if not content:
                continue

            # 按 Markdown 标题分割
            sections = self._split_by_headings(content)

            for heading, level, body in sections:
                if not body.strip():
                    continue

                # 如果块内容超过 chunk_size，进一步按段落切割
                sub_chunks = self._split_oversized(body, heading, level)

                for text in sub_chunks:
                    tok = self._estimate_tokens(text)
                    all_chunks.append(Chunk(
                        doc_title=title,
                        heading=heading,
                        heading_level=level,
                        text=text,
                        position=pos,
                        token_estimate=tok,
                    ))
                    pos += 1

        logger.debug("分块完成: %d 文档 → %d 块", len(documents), len(all_chunks))
        return all_chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, int, str]]:
        """按 Markdown 标题分割，返回 [(heading, level, body), ...]"""
        # 匹配 ## 或 ### 标题行
        pattern = re.compile(r"^(#{2,3})\s+(.+)$", re.MULTILINE)
        parts: list[tuple[str, int, str]] = []
        last_end = 0
        last_heading = ""
        last_level = 0

        for match in pattern.finditer(text):
            if last_end > 0:
                body = text[last_end:match.start()].strip()
                parts.append((last_heading, last_level, body))

            last_heading = match.group(2).strip()
            last_level = len(match.group(1))
            last_end = match.end()

        # 最后一段
        if last_end > 0:
            body = text[last_end:].strip()
            parts.append((last_heading, last_level, body))
        else:
            # 无标题，整体作为一段
            parts.append(("", 0, text.strip()))

        return parts

    def _split_oversized(self, text: str, heading: str, level: int) -> list[str]:
        """超长块按段落切割"""
        tok_count = self._estimate_tokens(text)
        if tok_count <= self.chunk_size:
            return [text]

        # 按空行分割为段落
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[str] = []
        current = ""
        current_tok = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_tok = self._estimate_tokens(para)

            if current_tok + para_tok > self.chunk_size and current:
                chunks.append(current)
                # 保留 overlap：从 current 尾部取 last few paragraphs
                overlap_text = self._get_overlap(current)
                current = overlap_text
                current_tok = self._estimate_tokens(overlap_text)

            if current:
                current += "\n\n" + para
            else:
                current = para
            current_tok = self._estimate_tokens(current)

        if current:
            chunks.append(current)

        return chunks

    def _get_overlap(self, text: str) -> str:
        """从文本尾部获取 overlap 长度的内容"""
        sentences = re.split(r"(?<=[。！？\n])", text)
        overlap_chars = self.overlap * 4  # 粗略：1 token ≈ 4 中文字符
        result = ""
        for sent in reversed(sentences):
            sent = sent.strip()
            if not sent:
                continue
            result = sent + result
            if len(result) >= overlap_chars:
                break
        return result

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """估算 token 数（中英文混合）"""
        if not text:
            return 0
        # 中文字符 ~1.5 token，其他字符 ~3.5 字符/token
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 3.5) + 1