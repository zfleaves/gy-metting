"""
多智能体工作流 (DESIGN.md §3.3 扩展)

编排 RAG 上下文准备 → 纪要生成 → 质量验证 三阶段流水线。
"""

from typing import AsyncGenerator, Optional

from src.log_utils import get_logger

logger = get_logger(__name__)

# 质量验证提示词 — 对抗式验证
VERIFY_PROMPT = """
你是一位**极其严格**的会议纪要质量审核专家。你的工作是对照【原始转写文本】找出会议纪要中的所有问题，**尽可能扣分**。

## 核心原则

- 你的角色是**对抗式审核**：主动找茬、逐条对比、绝不手软
- **如果找不出任何问题，说明你不够认真** — 真实的会议纪要必然有遗漏或不准确之处
- 必须引用转写文本中的具体语句作为扣分依据，禁止空泛扣分
- 宁可误判，不可放过：不确定时按有问题处理

## 强制扣分规则（逐项累加，满分100）

从 100 分开始，每发现一个问题按以下标准扣分：

1. **幻觉（编造内容）**：纪要中有转写文本完全不存在的决策、待办、结论 → 每条扣 **15-20分**
2. **决策遗漏**：转写文本中明确的决策未被收录 → 每条扣 **10-15分**
3. **待办遗漏**：转写文本中有「需要」「要」「必须」「负责」「跟进」「安排」「确认」「评估」「调研」「优化」「修改」「调整」「推动」「落实」等关键词的语句，但未提取为待办 → 每条扣 **8-10分**
4. **责任人缺失**：待办或决策没有责任人，且转写文本中能推断出谁负责 → 每条扣 **5-8分**
5. **参会人缺失**：转写文本中有人名（从「XX说」「XX认为」「XX提到」等句式），但未列入参会人 → 每条扣 **5分**
6. **内容矛盾**：纪要前后矛盾（如摘要说通过了，但评审结论写不通过） → 每条扣 **10分**
7. **格式问题**：Markdown 格式混乱、模块缺失（应该在的模块没出现） → 扣 **5分**

## 评分标准

- **≤ 30分**：严重问题，几乎全是编造或遗漏
- **31-50分**：大量问题，必须重写
- **51-69分**：有明显问题，需要修正
- **70-84分**：有少量问题，可修正
- **85-95分**：基本合格，有轻微瑕疵
- **≥ 96分**：几乎完美（极少出现，除非转写文本极短且内容完全覆盖）

## 输出格式

```
## 质量评分
总分: XX/100

## 问题列表
1. [严重/一般/轻微] 问题描述（证据：转写文本中「具体原文」）
2. [严重/一般/轻微] 问题描述（证据：转写文本中「具体原文」）

## 改进建议
- 建议 1
- 建议 2
```

**⚠️ 严格要求**：总分 ≤ 95，除非转写文本极短（<200字）且纪要完全准确。如果你给出的总分是100，请先反问自己：真的每一条待办都提取了吗？真的每一个决策都收录了吗？真的没有任何遗漏吗？
"""


def post_process_minutes(text: str) -> str:
    """
    纪要后处理：修复常见的一致性问题。

    * 旧版表格格式的兼容修复
    * 防止空洞的「未从会议文本识别参会人员」
    * 防止【未指定责任人】占位符出现在输出中
    """
    import re

    # 1. 参会人占位符修复（新格式+旧格式）
    text = re.sub(
        r'未从会议文本识别参会人员',
        '（发言角色待补充：建议根据转写文本中的发言内容补充参会角色）',
        text,
    )

    # 2. 【未指定责任人】→ 待确认（更友好的占位符）
    text = text.replace('【未指定责任人】', '待确认')
    text = text.replace('【时间待确认】', '待确认')

    # 3. 旧版兼容：如果输出仍是表格格式，走旧修复逻辑
    has_tables = '| 决策项 |' in text or '| 待办项 |' in text or '| 风险/问题 |' in text

    if has_tables:
        has_no_conclusion = '未形成明确评审结论' in text
        if has_no_conclusion and '### 关键决策' in text:
            text = text.replace('### 关键决策', '### 讨论方案汇总（待后续确认）', 1)
            if '| 决策项' in text and '| 状态 |' not in text:
                text = text.replace('| 决策项 | 决策内容 | 决策人 |', '| 决策项 | 决策内容 | 决策人 | 状态 |')
                text = text.replace('|--------|---------|--------|', '|--------|---------|--------|------|')
                lines = text.split('\n')
                fixed = []
                in_table = False
                for line in lines:
                    s = line.strip()
                    if s.startswith('| 决策项 | 决策内容 | 决策人 | 状态 |'):
                        in_table = True
                        fixed.append(line)
                        continue
                    if in_table:
                        if s.startswith('|---'):
                            fixed.append(line)
                            continue
                        if not s or not s.startswith('|'):
                            in_table = False
                            fixed.append(line)
                            continue
                        if s.startswith('|') and s.count('|') >= 3 and s.count('|') < 5:
                            line = line.rstrip() + ' 待确认 |'
                        fixed.append(line)
                        continue
                    fixed.append(line)
                text = '\n'.join(fixed)

        # 空表修复
        empty_table_patterns = [
            (r"### 风险与问题\n\| 风险/问题 \| 影响 \| 建议方案 \|\n\|-+\|-+\|-+\|\n\| 无 \| 无 \| 无 \|",
             "### 风险与问题\n> 本次会议未识别出风险与问题，无需处理"),
            (r"### 风险与问题\n\| 风险/问题 \| 影响 \| 建议方案 \|\n\|-+\|-+\|-+\|\n\| 无 \| 无 \| 无 \|\n\| 无 \| 无 \| 无 \|",
             "### 风险与问题\n> 本次会议未识别出风险与问题，无需处理"),
        ]
        for pattern, replacement in empty_table_patterns:
            text = re.sub(pattern, replacement, text)

        # 待办全部为占位符时加说明
        if "### 待办事项" in text:
            lines = text.split("\n")
            has_table = any("责任人" in l and "截止时间" in l for l in lines)
            if has_table:
                all_placeholder = True
                in_table = False
                for line in lines:
                    s = line.strip()
                    if "| 待办项" in s and "责任人" in s:
                        in_table = True
                        continue
                    if in_table:
                        if s.startswith("|---"):
                            continue
                        if not s or not s.startswith("|"):
                            break
                        cells = [c.strip() for c in s.split("|") if c.strip()]
                        if len(cells) >= 4:
                            resp = cells[1] if len(cells) > 1 else ""
                            deadline = cells[2] if len(cells) > 2 else ""
                            if resp != "待确认" or (deadline not in ("待确认", "【时间待确认】", "")):
                                all_placeholder = False
                                break
                if all_placeholder and "> ⚠️" not in text.rsplit("### 待办事项", 1)[-1].split("###", 1)[0]:
                    section = text.split("### 待办事项", 1)[-1]
                    next_heading = section.find("\n### ")
                    if next_heading > 0:
                        insert_pos = text.index("### 待办事项") + 6 + next_heading
                        text = (
                            text[:insert_pos]
                            + "\n> ⚠️ 以上待办均未在会议中明确责任人和截止时间，需会后补充确认\n"
                            + text[insert_pos:]
                        )

    # 4. 新格式兜底：如果待办列表全部是「待确认」，也加提醒
    if '### 待办事项' in text and not has_tables:
        todo_section = text.split('### 待办事项', 1)[-1].split('###', 1)[0]
        # 检查是否所有待办都是 @待确认
        todo_lines = [l.strip() for l in todo_section.split('\n') if l.strip().startswith('- ') and '@待确认' in l]
        total_todos = [l.strip() for l in todo_section.split('\n') if l.strip().startswith('- ')]
        if todo_lines and len(todo_lines) == len(total_todos) and len(total_todos) > 0:
            text = text.replace(
                '### 待办事项',
                '### 待办事项\n> ⚠️ 以上待办均未在会议中明确责任人和截止时间，需会后补充确认\n',
            )

    return text


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
        {"type": "phase", "phase": "rag|generating|verifying|fixing|done", "message": "..."}
        {"type": "chunk", "text": "..."}
        {"type": "verify_result", "score": 85, "issues": [...], "suggestions": [...]}
        {"type": "error", "message": "..."}
    """
    # ---- 预提取转写文本（供后续修正循环使用） ----
    transcript = ""
    try:
        from src.llm.context import load_task_context
        ctx = load_task_context(task_id)
        transcript = ctx.get("transcript", "")
    except Exception:
        pass

    # ---- Phase 1: RAG 上下文优化 ----
    if rag_enabled:
        yield {"type": "phase", "phase": "rag", "message": "正在检索参考文档..."}
        try:
            from src.llm.rag import get_rag_context

            if ctx.get("documents"):
                # 构建查询文本：背景 + 转写摘要
                query_parts = []
                if ctx.get("background"):
                    query_parts.append(ctx["background"])
                trans = ctx.get("transcript", "")
                if trans:
                    query_parts.append(trans[:2000])  # 取转写前 2000 字作为查询
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

    # ---- Phase 2.5: 后处理一致性校验 ----
    processed = post_process_minutes(full_text)
    if processed != full_text:
        diff_lines = sum(1 for a, b in zip(full_text.split("\n"), processed.split("\n")) if a != b)
        diff_lines += abs(len(full_text.split("\n")) - len(processed.split("\n")))
        full_text = processed
        yield {"type": "chunk", "text": f"\n\n> 🔧 自动修复 {diff_lines} 处格式/一致性问题\n\n"}

    # ---- Phase 3: 质量验证 + 自动修正循环 ----
    if verify_enabled and full_text:
        yield {"type": "phase", "phase": "verifying", "message": "正在验证纪要质量..."}

        import re

        MAX_FIX_ITERATIONS = 2  # 最多 1 轮修正：验证 → 修正 → 再验证 → 结束
        fix_iteration = 0

        while fix_iteration < MAX_FIX_ITERATIONS:
            fix_iteration += 1
            try:
                verify_messages = [
                    {"role": "system", "content": VERIFY_PROMPT},
                    {"role": "user", "content": (
                        f"## 原始转写文本\n\n{transcript[:8000] if transcript else '（无转写文本）'}\n\n"
                        f"## 待审核的会议纪要\n\n{full_text}\n\n"
                        "请严格对照原始转写文本逐条核实，指出纪要中与原文不符、遗漏、虚构的内容。"
                    )},
                ]
                verify_result = ""
                async for chunk in adapter.chat(
                    messages=verify_messages,
                    temperature=0.1,
                    max_tokens=1024,
                    stream=True,
                ):
                    if chunk:
                        verify_result += chunk

                # 解析验证结果
                score = 50  # 默认 50 分（严格），只有 LLM 明确给出总分才覆盖
                issues = []
                suggestions = []

                logger.debug("验证原始输出: %s", verify_result[:500] if verify_result else "(空)")

                score_match = re.search(r"总分:\s*(\d+)", verify_result)
                if score_match:
                    score = int(score_match.group(1))

                if "## 问题列表" in verify_result:
                    issue_section = verify_result.split("## 问题列表")[-1]
                    issue_section = issue_section.split("## 改进建议")[0] if "## 改进建议" in issue_section else issue_section
                    for line in issue_section.split("\n"):
                        line = line.strip()
                        if line.startswith(("- ", "1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")):
                            issues.append(re.sub(r"^\d+[.、]\s*", "", line).lstrip("- "))

                if "## 改进建议" in verify_result:
                    suggest_section = verify_result.split("## 改进建议")[-1]
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
                    "iteration": fix_iteration,
                }

                # 如果已经 >= 60 分，或者已经是初版之后的修正循环了
                if score >= 60:
                    yield {"type": "status", "message": f"✅ 质量评分: {score}/100"}
                    break

                if fix_iteration >= MAX_FIX_ITERATIONS:
                    yield {"type": "status", "message": f"⚠️ 经{MAX_FIX_ITERATIONS}轮修正后评分仍为{score}/100，请手动检查"}
                    break

                # ---- 自动修正：评分 < 60，启动修正循环 ----
                logger.warning("纪要质量评分偏低(%d/100)，启动第%d轮修正", score, fix_iteration)
                yield {"type": "status", "message": f"⚠️ 质量评分: {score}/100（第{fix_iteration}轮），正在根据审核意见修正..."}

                # 构建修复提示词（含原始转写文本）
                fix_prompt = (
                    "你是一位会议纪要修正专家。以下是一份 AI 生成的会议纪要初稿，"
                    "经质量审核发现以下问题。只输出修正后的完整纪要正文，不要加任何解释、说明、开头语或结尾语。\n\n"
                )

                # 关键：传入原始转写文本，让 LLM 可以从中提取遗漏信息
                if transcript:
                    # 截取前 10000 字，避免超长
                    truncated_transcript = transcript[:10000]
                    fix_prompt += (
                        f"## 原始会议转写文本（最重要信息来源，从中提取遗漏信息）\n\n"
                        f"{truncated_transcript}\n"
                        f"{'…（以下省略）' if len(transcript) > 10000 else ''}\n\n"
                    )

                fix_prompt += (
                    f"## 当前纪要（需要修正的版本）\n\n{full_text}\n\n"
                    f"## 需要修正的问题\n\n"
                )
                for i, issue in enumerate(issues):
                    fix_prompt += f"{i+1}. {issue}\n"
                if suggestions:
                    fix_prompt += f"\n## 改进建议\n\n"
                    for s in suggestions:
                        fix_prompt += f"- {s}\n"

                fix_prompt += (
                    "\n## 修正要求（必须严格遵守）\n"
                    "1. 输出**完整的、修正后的**会议纪要，不要只输出修正部分；\n"
                    "2. 必须仔细阅读原始转写文本，从文本中提取遗漏的决策、待办、参会人信息；\n"
                    "3. 决策表每条都必须指定具体决策人——从转写文本中找谁说的、谁拍板的；\n"
                    "   如果只能推断角色（如「产品说」→产品经理），填角色而非占位符；\n"
                    "   只有在完全找不到任何线索时才填「待确认」；\n"
                    "4. 待办表必须覆盖所有未决事项——从转写文本中找「需要」「要」「必须」「负责」「跟进」等关键词；\n"
                    "   每条待办必须有责任人和大致截止时间，找不到责任人填「待确认」而非「【未指定责任人】」；\n"
                    "5. 参会人栏必须填写——从转写文本中提取所有提到的人名、角色、称呼；\n"
                    "6. 确保全文逻辑一致：摘要内容、决策表、待办表之间不能互相矛盾；\n"
                    "7. 严格保持原始 Markdown 格式不变。"
                )

                yield {"type": "phase", "phase": "fixing", "message": f"正在根据审核意见修正纪要（第{fix_iteration}轮）..."}

                fix_messages = [
                    {"role": "system", "content": fix_prompt},
                    {"role": "user", "content": "请参考原始转写文本，修正以上会议纪要中的问题，输出完整修正版。"},
                ]

                new_text = ""
                async for chunk in adapter.chat(
                    messages=fix_messages,
                    temperature=0.1,  # 修正时低温度，确定性修正
                    max_tokens=max_tokens,
                    stream=True,
                ):
                    if chunk:
                        new_text += chunk
                # 不 yield chunk 避免与已有内容拼接重复

                if new_text:
                    # 修正后再过一次后处理
                    new_text = post_process_minutes(new_text)
                    full_text = new_text
                    yield {"type": "status", "message": f"🔄 第{fix_iteration}轮修正完成，重新验证..."}
                else:
                    yield {"type": "status", "message": f"⚠️ 第{fix_iteration}轮修正无输出，保留原始版本"}
                    break

            except Exception as e:
                logger.warning("验证/修正阶段失败(第%d轮): %s", fix_iteration, e)
                yield {"type": "status", "message": f"⚠️ 验证/修正异常: {e}，保留当前版本"}
                break

    yield {"type": "done", "text": full_text}


from src.llm.rag import RagEngine  # noqa: E402, F811