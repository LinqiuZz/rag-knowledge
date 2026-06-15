"""RAG 评估模块"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class RAGEvaluation:
    """RAG 评估结果"""
    query: str
    answer: str
    sources: list[dict]
    metrics: dict


@dataclass
class RetrievalMetrics:
    """检索评估指标"""
    precision_at_k: float  # 精确率
    recall_at_k: float     # 召回率
    mrr: float             # 平均倒数排名
    ndcg_at_k: float       # 归一化折损累积增益


@dataclass
class GenerationMetrics:
    """生成评估指标"""
    faithfulness: float    # 忠实度（回答是否基于检索结果）
    relevance: float       # 相关性（回答是否与问题相关）
    completeness: float    # 完整性（回答是否完整）


def evaluate_retrieval(
    query: str,
    retrieved_docs: list[dict],
    relevant_docs: list[str],
    k: int = 5,
) -> RetrievalMetrics:
    """
    评估检索质量

    Args:
        query: 查询
        retrieved_docs: 检索到的文档列表
        relevant_docs: 相关文档列表（ground truth）
        k: top-k

    Returns:
        检索评估指标
    """
    if not retrieved_docs or not relevant_docs:
        return RetrievalMetrics(0.0, 0.0, 0.0, 0.0)

    # 计算 Precision@K
    retrieved_at_k = retrieved_docs[:k]
    relevant_set = set(relevant_docs)
    relevant_retrieved = sum(
        1 for doc in retrieved_at_k
        if doc.get("source", "") in relevant_set
    )
    precision_at_k = relevant_retrieved / k if k > 0 else 0.0

    # 计算 Recall@K
    recall_at_k = relevant_retrieved / len(relevant_set) if relevant_set else 0.0

    # 计算 MRR (Mean Reciprocal Rank)
    mrr = 0.0
    for i, doc in enumerate(retrieved_docs):
        if doc.get("source", "") in relevant_set:
            mrr = 1.0 / (i + 1)
            break

    # 计算 NDCG@K
    dcg = sum(
        1.0 / (i + 1) for i, doc in enumerate(retrieved_at_k)
        if doc.get("source", "") in relevant_set
    )
    ideal_dcg = sum(1.0 / (i + 1) for i in range(min(len(relevant_set), k)))
    ndcg_at_k = dcg / ideal_dcg if ideal_dcg > 0 else 0.0

    return RetrievalMetrics(
        precision_at_k=precision_at_k,
        recall_at_k=recall_at_k,
        mrr=mrr,
        ndcg_at_k=ndcg_at_k,
    )


def evaluate_generation(
    query: str,
    answer: str,
    context: str,
    llm=None,
) -> GenerationMetrics:
    """
    评估生成质量（使用 LLM 自动评估）

    Args:
        query: 查询
        answer: 生成的回答
        context: 检索到的上下文
        llm: LLM 实例（可选）

    Returns:
        生成评估指标
    """
    if llm is None:
        # 简单的规则评估（无 LLM 时）
        return _rule_based_evaluation(query, answer, context)

    # 使用 LLM 进行评估
    eval_prompt = f"""请评估以下 RAG 问答的质量：

**问题**: {query}

**检索到的上下文**:
{context}

**生成的回答**:
{answer}

请从以下三个维度打分（0-10分）：

1. **忠实度**: 回答是否完全基于检索到的上下文，没有编造信息
2. **相关性**: 回答是否与问题相关
3. **完整性**: 回答是否完整地回答了问题

请用 JSON 格式回复：
{{"faithfulness": <分数>, "relevance": <分数>, "completeness": <分数>}}
"""

    try:
        response = llm.chat("你是评估专家。", eval_prompt)
        import json
        scores = json.loads(response)
        return GenerationMetrics(
            faithfulness=scores.get("faithfulness", 5) / 10,
            relevance=scores.get("relevance", 5) / 10,
            completeness=scores.get("completeness", 5) / 10,
        )
    except Exception:
        return _rule_based_evaluation(query, answer, context)


def _rule_based_evaluation(
    query: str, answer: str, context: str
) -> GenerationMetrics:
    """基于规则的简单评估"""
    # 忠实度：回答中包含上下文关键词的比例
    context_words = set(context.split())
    answer_words = set(answer.split())
    overlap = len(context_words & answer_words)
    faithfulness = min(overlap / max(len(answer_words), 1), 1.0)

    # 相关性：回答中包含查询关键词的比例
    query_words = set(query.split())
    relevance = len(query_words & answer_words) / max(len(query_words), 1)

    # 完整性：回答长度与查询复杂度的比值
    completeness = min(len(answer) / max(len(query) * 10, 1), 1.0)

    return GenerationMetrics(
        faithfulness=faithfulness,
        relevance=relevance,
        completeness=completeness,
    )


def rag_evaluate(
    query: str,
    answer: str,
    sources: list[dict],
    context: str,
    relevant_docs: Optional[list[str]] = None,
    llm=None,
    k: int = 5,
) -> RAGEvaluation:
    """
    完整的 RAG 评估

    Args:
        query: 查询
        answer: 生成的回答
        sources: 引用来源
        context: 检索到的上下文
        relevant_docs: 相关文档列表（ground truth，可选）
        llm: LLM 实例（可选）
        k: top-k

    Returns:
        RAG 评估结果
    """
    metrics = {}

    # 检索评估（需要 ground truth）
    if relevant_docs:
        retrieval_metrics = evaluate_retrieval(query, sources, relevant_docs, k)
        metrics["retrieval"] = {
            "precision_at_k": retrieval_metrics.precision_at_k,
            "recall_at_k": retrieval_metrics.recall_at_k,
            "mrr": retrieval_metrics.mrr,
            "ndcg_at_k": retrieval_metrics.ndcg_at_k,
        }

    # 生成评估
    generation_metrics = evaluate_generation(query, answer, context, llm)
    metrics["generation"] = {
        "faithfulness": generation_metrics.faithfulness,
        "relevance": generation_metrics.relevance,
        "completeness": generation_metrics.completeness,
    }

    return RAGEvaluation(
        query=query,
        answer=answer,
        sources=sources,
        metrics=metrics,
    )
