"""
多智能体工作流 (DESIGN.md §3.3 扩展)

编排 RAG 上下文准备 → 纪要生成 → 质量验证 三阶段流水线。
"""

from typing import AsyncGenerator, Optional

from src.log_utils import get_logger

logger = get_logger(__name__)

# 质量验证提示词
VERIFY_PROMPT = """
你是一位会议纪要质量审核专家。请严格审核以下会议纪要。

## 检查维度

1. **幻觉检测**：纪要中是否有转写文本中未提及的观点、决策或数据？
2. **决策完整性**：是否遗漏了会议中明确做出的决策？
3. **待办清晰度**：每个待办事项是否有明确的责任人（@某人）和时间要求？
4. **变更记录**：涉及需求/方案变更时，是否标注了"变更前"和"变更后"？
5. **格式合规**：是否严格遵循 Markdown 输出格式规范？

## 输出格式

```
## 质量评分
总分: XX/100

## 问题列表
1. [严重/一般/轻微] 问题描述

## 改进建议
- 建议 1
- 建议 2
```

注意：如果没有问题，请输出"质量审核通过，无需修改。"
"""


async def run_minutes_workflow(
    task_id: str,
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 8192,
    rag_enabled: bool = True,
    verify_enabled: bool = False,
) -> AsyncGenerator[dict, None]:
    """
    多智能体纪要生成工作流。

    Yields:
        {"type": "phase", "phase": "rag|generating|verifying|done", "message": "..."}
        {"type": "chunk", "text": "..."}
        {"type": "verify_result", "score": 85, "issues": [...], "suggestions": [...]}
        {"type": "error", "message": "..."}
    """
    # ---- Phase 1: RAG 上下文优化 ----
    if rag_enabled:
        yield {"type": "phase", "phase": "rag", "message": "正在检索参考文档..."}
        try:
            from src.llm.context import load_task_context
            from src.llm.rag import get_rag_context

            ctx = load_task_context(task_id)
            if ctx.get("documents"):
                # 构建查询文本：背景 + 转写摘要
                query_parts = []
                if ctx.get("background"):
                    query_parts.append(ctx["background"])
                transcript = ctx.get("transcript", "")
                if transcript:
                    query_parts.append(transcript[:2000])  # 取转写前 2000 字作为查询
                query = "\n".join(query_parts) if query_parts else ctx["title"]

                rag_context = await get_rag_context(query, ctx["documents"])

                if rag_context and rag_context != RagEngine._fallback_truncate(ctx["documents"]):
                    # 替换 messages 中参考文档部分
                    for i, msg in enumerate(messages):
                        if msg.get("role") == "user" and "参考文档" in (msg.get("content") or ""):
                            doc_msg = (
                                f"## 参考文档（RAG 检索增强）\n\n"
                                f"{rag_context}\n\n"
                                f"注意：以上为语义检索后最相关的文档内容，"
                                f"仅作为业务基线参考，会上未讨论的内容严禁输出评审结论。"
                            )
                            messages[i] = {"role": "user", "content": doc_msg}
                            yield {"type": "chunk", "text": "[RAG 上下文已优化]\n\n"}
                            break

                logger.info("RAG 上下文已应用: task=%s", task_id)
        except Exception as e:
            logger.warning("RAG 阶段失败，降级为原始上下文: %s", e)
            yield {"type": "chunk", "text": "[RAG 检索异常，使用原始上下文继续]\n\n"}

    # ---- Phase 2: 纪要生成 ----
    yield {"type": "phase", "phase": "generating", "message": "正在生成会议纪要..."}

    from src.llm.adapter import get_llm_adapter
    adapter = get_llm_adapter()

    full_text = ""
    try:
        async for chunk in adapter.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        ):
            if chunk:
                full_text += chunk
                yield {"type": "chunk", "text": chunk}
    except Exception as e:
        logger.error("生成阶段失败: %s", e)
        yield {"type": "error", "message": f"纪要生成失败: {e}"}
        return

    # ---- Phase 3: 质量验证 ----
    if verify_enabled and full_text:
        yield {"type": "phase", "phase": "verifying", "message": "正在验证纪要质量..."}
        try:
            verify_messages = [
                {"role": "system", "content": VERIFY_PROMPT},
                {"role": "user", "content": f"请审核以下会议纪要：\n\n{full_text}"},
            ]
            verify_result = ""
            async for chunk in adapter.chat(
                messages=verify_messages,
                temperature=0.1,  # 验证时低温度，更严格
                max_tokens=1024,
                stream=True,
            ):
                if chunk:
                    verify_result += chunk

            # 解析验证结果
            score = 100
            issues = []
            suggestions = []

            import re
            score_match = re.search(r"总分:\s*(\d+)", verify_result)
            if score_match:
                score = int(score_match.group(1))

            if "问题列表" in verify_result or "问题" in verify_result:
                # 提取问题
                issue_section = verify_result.split("## 问题列表")[-1] if "## 问题列表" in verify_result else ""
                issue_section = issue_section.split("## 改进建议")[0] if "## 改进建议" in issue_section else issue_section
                for line in issue_section.split("\n"):
                    line = line.strip()
                    if line.startswith(("- ", "1.", "2.", "3.", "4.", "5.")):
                        issues.append(line.lstrip("1234567890. -"))

            if "改进建议" in verify_result:
                suggest_section = verify_result.split("## 改进建议")[-1] if "## 改进建议" in verify_result else ""
                for line in suggest_section.split("\n"):
                    line = line.strip()
                    if line.startswith("- "):
                        suggestions.append(line[2:])

            yield {
                "type": "verify_result",
                "score": score,
                "issues": issues,
                "suggestions": suggestions,
                "raw": verify_result,
            }

            if score < 60:
                logger.warning("纪要质量评分偏低: %d/100", score)
                yield {"type": "chunk", "text": f"\n\n> ⚠️ 质量评分: {score}/100，建议检查后重新生成\n\n"}
            else:
                yield {"type": "chunk", "text": f"\n\n> ✅ 质量评分: {score}/100\n\n"}

        except Exception as e:
            logger.warning("验证阶段失败: %s", e)

    yield {"type": "done", "text": full_text}


from src.llm.rag import RagEngine  # noqa: E402, F811