"""
OpenAI 兼容模式 LLM 适配器 (DESIGN.md §3.3.1)

支持 DeepSeek、通义千问、GLM 等所有 OpenAI 兼容 API。
流式输出使用 SSE (Server-Sent Events)。
"""

import json
import re
from typing import AsyncGenerator, Optional

import httpx

from src.log_utils import get_logger

logger = get_logger(__name__)


class OpenAICompatAdapter:
    """OpenAI 兼容模式适配器"""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 120,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.3,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> AsyncGenerator[str, None]:
        """统一聊天接口"""
        url = f"{self.base_url.rstrip('/')}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            if stream:
                full_content = ""
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    if resp.status_code != 200:
                        error_body = await resp.aread()
                        error_text = error_body.decode()
                        logger.error("LLM API 错误: status=%d body=%s", resp.status_code, error_text)
                        yield f"【API 错误 {resp.status_code}】: {error_text}"
                        return

                    # 使用 aiter_bytes 逐块读取，避免 aiter_lines 缓冲
                    buf = ""
                    async for chunk in resp.aiter_bytes():
                        buf += chunk.decode()
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            line = line.strip()
                            if not line.startswith("data: "):
                                continue
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            try:
                                data = json.loads(data_str)
                                choices = data.get("choices", [])
                                if not choices:
                                    continue
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    full_content += content
                                    yield content
                            except json.JSONDecodeError:
                                continue

                # 如果流式没有返回内容，尝试非流式
                if not full_content:
                    logger.info("流式返回为空，尝试非流式请求")
                    payload["stream"] = False
                    resp = await client.post(url, json=payload, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                        if content:
                            yield content
            else:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code != 200:
                    try:
                        err = resp.json()
                        detail = err.get("error", {}).get("message", str(resp.text))
                    except Exception:
                        detail = resp.text
                    logger.error("LLM API 错误: status=%d, %s", resp.status_code, detail)
                    yield f"【API 错误 {resp.status_code}】: {detail}"
                    return

                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                yield content

    def count_tokens(self, text: str) -> int:
        """估算 token 数量（中文约 1.5 字/token，英文约 3.5 字符/token）"""
        if not text:
            return 0
        # 粗略估算
        chinese_chars = len(re.findall(r"[一-鿿]", text))
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars / 3.5)