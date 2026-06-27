"""查询改写模块 — 三大核心策略

三大策略可独立或组合使用，执行顺序:
  1. 上下文补全 (Context Compress)  — 指代消解 + 查询压缩
  2. 任务分解   (Task Decompose)    — Step-back + 子查询拆解
  3. 语义增强   (HyDE)              — 假设文档嵌入

用法:
    rewriter = QueryRewriter(settings, llm)
    plans = rewriter.rewrite("Q3营收情况如何？", history=[...])
    # plans = [RewritePlan(queries=[...], strategy="...")]

集成到检索管道:
    pipeline = RetrievalPipeline(settings, llm=llm)
    result = pipeline.retrieve(query, ..., use_rewrite=True)
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class RewritePlan:
    """改写计划 — 一次改写产出的所有检索查询。"""
    queries: list[str]              # 改写后的查询列表
    strategy: str                   # 使用的策略: compress | decompose | hyde | combined
    original: str                   # 原始查询
    rationale: str = ""             # 改写理由（调试用）


# ═══════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════

class QueryRewriter:
    """查询改写器 — 编排三大策略。

    Args:
        settings: 系统配置
        llm:      LLM 实例（三大策略均依赖 LLM）

    用法:
        rewriter = QueryRewriter(settings, llm)
        plans = rewriter.rewrite(
            query="Q3营收情况如何？",
            history=[{"role":"user","content":"上季度业绩"}, ...],
            use_compress=True,
            use_decompose=True,
            use_hyde=True,
        )
    """

    def __init__(self, settings, llm=None):
        self.settings = settings
        self.llm = llm

    def rewrite(
        self,
        query: str,
        history: list[dict] = None,
        use_compress: bool = True,
        use_decompose: bool = True,
        use_hyde: bool = False,
    ) -> list[RewritePlan]:
        """对查询执行三阶段改写。

        返回 RewritePlan 列表。通常返回 1 个 plan，
        但 decompose 可能返回多个子查询，每个子查询再各自 HyDE。

        Args:
            query: 原始用户查询
            history: 多轮对话历史 [{"role": "user/assistant", "content": "..."}]
            use_compress: 是否启用上下文补全（指代消解 + 压缩）
            use_decompose: 是否启用任务分解
            use_hyde: 是否启用语义增强（HyDE）

        Returns:
            list[RewritePlan]
        """
        if not self.llm:
            logger.debug("LLM 不可用，跳过查询改写")
            return [RewritePlan(queries=[query], strategy="passthrough", original=query)]

        plans = []
        current_query = query

        # ── Step 1: 上下文补全 ──
        if use_compress and history:
            compressed = self.compress_context(query, history)
            if compressed != query:
                logger.debug("上下文补全: %r → %r", query, compressed)
            current_query = compressed

        # ── Step 2: 任务分解 ──
        if use_decompose:
            sub_queries = self.decompose(current_query)
            if len(sub_queries) > 1:
                logger.debug("任务分解: %r → %r", current_query, sub_queries)
            else:
                sub_queries = [current_query]
        else:
            sub_queries = [current_query]

        # ── Step 3: HyDE 对每个子查询独立执行 ──
        if use_hyde:
            hyde_queries = []
            rationale_parts = []
            for sq in sub_queries:
                hypo = self.hyde(sq)
                hyde_queries.append(hypo)
                rationale_parts.append(f"{sq} → [假设文档]")
            logger.debug("HyDE 改写: %d 个子查询", len(hyde_queries))
            plans.append(RewritePlan(
                queries=hyde_queries,
                strategy="hyde",
                original=query,
                rationale="; ".join(rationale_parts),
            ))
        else:
            strategy = "compress" if use_compress else "decompose" if use_decompose else "passthrough"
            plans.append(RewritePlan(
                queries=sub_queries,
                strategy=strategy,
                original=query,
            ))

        return plans

    # ───────────────────────────────────────────────────────────
    # 策略一: 上下文补全 (Context Compress)
    # ───────────────────────────────────────────────────────────

    def compress_context(self, query: str, history: list[dict]) -> str:
        """指代消解 + 查询压缩。

        将多轮历史"脱水"，把省略、指代补全，
        形成独立完整的检索句子。

        输入:
          history: [{"role":"user","content":"什么是RAG"},
                    {"role":"assistant","content":"RAG是..."},
                    {"role":"user","content":"它的优缺点呢"}]
          query: "它的优缺点呢"

        输出: "RAG技术的优缺点"
        """
        if not history:
            return query

        # 构建压缩 prompt
        history_text = _format_history(history)

        prompt = f"""你是一个查询压缩专家。根据对话历史，将当前问题改写为一个**独立、完整、适合检索**的句子。

规则:
1. 消除所有指代（"它"、"这个"、"该方法"等），用具体实体替换
2. 补全省略的主语/宾语
3. 保留关键术语和实体名
4. 输出仅一行改写后的查询，不要解释

【示例】
对话历史:
用户: 什么是RAG技术？
助手: RAG（检索增强生成）是一种结合信息检索和大语言模型的技术...
用户: 它的优缺点呢？

当前问题: 它的优缺点呢？
改写后的独立查询: RAG技术（检索增强生成）的优缺点

对话历史:
{history_text}

当前问题: {query}

改写后的独立查询:"""

        try:
            response = self.llm.chat("你是查询压缩专家。", prompt)
            compressed = response.strip().strip('"').strip("'").split("\n")[0].strip()
            return compressed if compressed else query
        except Exception as e:
            logger.warning("上下文补全失败: %s", e)
            return query

    # ───────────────────────────────────────────────────────────
    # 策略二: 任务分解 (Task Decompose)
    # ───────────────────────────────────────────────────────────

    def decompose(self, query: str) -> list[str]:
        """Step-back + 子查询拆解。

        将复杂问题拆分为多个简单的粒度更细的检索单元。

        策略:
          a) Step-back: 先问一个更高层次的抽象问题
          b) 子查询: 将并列/对比问题拆成独立子查询

        输入: "比较RAG和Fine-tuning的优缺点及适用场景"
        输出: [
            "RAG技术的优势和局限",           # 子查询 A
            "Fine-tuning的优势和局限",       # 子查询 B
            "RAG与Fine-tuning的适用场景对比", # 子查询 C
            "检索增强生成技术概述",           # Step-back 抽象问题
        ]
        """
        # 快速启发式: 简短问题不需要分解
        if len(query) < 15 and "比较" not in query and "对比" not in query:
            return [query]

        prompt = f"""你是一个查询分解专家。将复杂问题拆解为适合独立检索的子查询。

拆解规则:
1. 如果问题包含"比较/对比/A和B"，为每个比较对象生成独立查询
2. 如果问题包含多个并列子问题，拆成独立查询
3. 添加一个 Step-back 查询：更高层次的概括性问题（帮助召回背景知识）
4. 每个子查询应该独立、完整、适合向量检索
5. 子查询数量控制在 2-4 个

【示例】
问题: 比较RAG和Fine-tuning的优缺点及适用场景
思考过程: 该问题包含两个比较对象（RAG、Fine-tuning），需分别检索各自的优缺点，再检索对比信息，并补充一个背景知识查询。
输出: {{"sub_queries": ["RAG技术的优势和局限", "Fine-tuning的优势和局限", "RAG与Fine-tuning的适用场景对比"], "step_back": "检索增强生成技术概述"}}

问题: {query}

请先分析问题结构（涉及哪些实体、关系、是否包含比较/并列），再拆解。
请用 JSON 格式回复:
{{"sub_queries": ["子查询1", "子查询2", "子查询3"], "step_back": "Step-back概括问题"}}"""

        try:
            response = self.llm.chat("你是查询分解专家。", prompt)
            result = _extract_json(response)

            sub_queries = result.get("sub_queries", [])
            step_back = result.get("step_back", "")

            # 合并: step_back + sub_queries（去重，step_back 放最前面）
            all_queries = []
            if step_back and step_back not in sub_queries:
                all_queries.append(step_back)
            for sq in sub_queries:
                sq = sq.strip()
                if sq and sq not in all_queries:
                    all_queries.append(sq)

            return all_queries if all_queries else [query]

        except Exception as e:
            logger.warning("任务分解失败: %s", e)
            return [query]

    # ───────────────────────────────────────────────────────────
    # 策略三: 语义增强 (HyDE)
    # ───────────────────────────────────────────────────────────

    def hyde(self, query: str) -> str:
        """假设文档嵌入 (Hypothetical Document Embedding)。

        原理: 让 LLM 先生成一个"假答案"（假设文档），
        然后用这个假答案的文本作为检索查询向量化，
        而不是用原始问题。

        假答案比问题更接近知识库中真实文档的语义空间，
        因此能显著提升召回相关度。

        输入: "什么是梯度下降？"
        输出: "梯度下降是一种优化算法，通过计算损失函数的梯度来
               更新模型参数，使损失函数逐步减小。常用变体包括
               批量梯度下降、随机梯度下降和小批量梯度下降..."
        """
        prompt = f"""你是一个知识库检索助手。请根据问题生成一段**假设性的参考文档**，仿佛这个问题已经被知识库中的文档完美回答了。

要求:
1. 生成 150-300 字的假设文档片段
2. 使用专业、客观的文档风格（不是对话风格）
3. 包含与问题相关的关键术语和概念
4. 假设文档来自企业内部知识库
5. 不要标注来源，直接输出文档内容

【示例】
问题: 什么是梯度下降？
假设文档: 梯度下降（Gradient Descent）是机器学习中最基础的优化算法之一，通过迭代地沿损失函数梯度的反方向更新模型参数来最小化损失函数。其核心思想是：计算损失函数关于每个参数的偏导数（梯度），然后用学习率控制更新步长，使参数逐步收敛到局部最优解。常见变体包括批量梯度下降（BGD，使用全部样本计算梯度）、随机梯度下降（SGD，每次使用单个样本）和小批量梯度下降（Mini-batch GD，使用小批量样本）。学习率的选择对收敛速度和稳定性有决定性影响。

问题: {query}

假设文档:"""

        try:
            response = self.llm.chat(
                "你是一个知识库文档生成专家。生成假设性的参考文档片段。",
                prompt,
            )
            hypo_doc = response.strip()
            # 取前 300 字，避免过长影响嵌入质量
            if len(hypo_doc) > 600:
                hypo_doc = hypo_doc[:600]
            return hypo_doc if hypo_doc else query
        except Exception as e:
            logger.warning("HyDE 生成失败: %s", e)
            return query


# ═══════════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════════

def _format_history(history: list[dict]) -> str:
    """将对话历史格式化为可读文本。"""
    lines = []
    for msg in history[-6:]:  # 最多取最近 6 轮
        role = "用户" if msg.get("role") == "user" else "助手"
        content = msg.get("content", "")
        # 截断过长的历史
        if len(content) > 300:
            content = content[:300] + "..."
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _extract_json(text: str) -> dict:
    """从 LLM 响应中提取 JSON。"""
    # 尝试 ```json ... ``` 块
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
    if match:
        return json.loads(match.group(1))

    # 尝试直接解析
    # 跳过前缀文字，找到 { 开始
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        return json.loads(text[start:end + 1])

    return {}
