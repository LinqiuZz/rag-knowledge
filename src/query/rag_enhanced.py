"""增强的 RAG 链"""

from __future__ import annotations

from typing import Optional
from dataclasses import dataclass


@dataclass
class RAGResult:
    """RAG 结果"""
    answer: str
    sources: list[dict]
    context: str
    query: str
    enhanced_query: Optional[str] = None


def multi_query_search(
    query: str,
    vector_store,
    embedder,
    llm=None,
    top_k: int = 5,
    num_queries: int = 3,
) -> list[dict]:
    """
    多查询检索（Query Expansion）

    通过 LLM 生成多个相关查询，提高检索召回率

    Args:
        query: 原始查询
        vector_store: 向量存储
        embedder: 嵌入管理器
        llm: LLM 实例（可选）
        top_k: 每个查询返回的结果数
        num_queries: 生成的查询数量

    Returns:
        去重后的检索结果
    """
    from .search import semantic_search

    # 原始查询的结果
    all_results = semantic_search(query, vector_store, embedder, top_k=top_k)

    if llm is None:
        return all_results

    # 使用 LLM 生成多个相关查询
    query_gen_prompt = f"""请根据以下查询生成 {num_queries} 个相关但不同角度的查询，用于提高检索召回率。

原始查询: {query}

请用 JSON 格式回复，包含一个查询列表：
{{"queries": ["查询1", "查询2", "查询3"]}}
"""

    try:
        response = llm.chat("你是查询扩展专家。", query_gen_prompt)
        import json
        queries = json.loads(response).get("queries", [])
    except Exception:
        queries = []

    # 对每个扩展查询进行检索
    seen_sources = {r.source for r in all_results}
    for expanded_query in queries[:num_queries]:
        results = semantic_search(expanded_query, vector_store, embedder, top_k=top_k)
        for r in results:
            if r.source not in seen_sources:
                all_results.append(r)
                seen_sources.add(r.source)

    return all_results


def rerank_results(
    query: str,
    results: list,
    llm=None,
    top_k: int = 5,
) -> list:
    """
    结果重排序

    使用 LLM 对检索结果进行重排序，提高相关性

    Args:
        query: 查询
        results: 检索结果
        llm: LLM 实例（可选）
        top_k: 返回的结果数

    Returns:
        重排序后的结果
    """
    if llm is None or len(results) <= top_k:
        return results[:top_k]

    # 使用 LLM 进行重排序
    docs_text = "\n\n".join([
        f"[文档{i+1}] {r.title}\n{r.text[:200]}..."
        for i, r in enumerate(results[:10])  # 最多处理10个文档
    ])

    rerank_prompt = f"""请根据查询对以下文档进行相关性排序。

查询: {query}

文档列表:
{docs_text}

请返回最相关的 {top_k} 个文档编号（JSON格式）：
{{"ranked_indices": [1, 3, 5, 2, 4]}}
"""

    try:
        response = llm.chat("你是文档排序专家。", rerank_prompt)
        import json
        ranked_indices = json.loads(response).get("ranked_indices", [])
        # 重排序结果
        reranked = []
        for idx in ranked_indices[:top_k]:
            if 1 <= idx <= len(results):
                reranked.append(results[idx - 1])
        return reranked if reranked else results[:top_k]
    except Exception:
        return results[:top_k]


def enhanced_rag_answer(
    query: str,
    settings,
    vector_store,
    embedder,
    llm,
    top_k: int = 5,
    use_multi_query: bool = False,
    use_rerank: bool = False,
) -> dict:
    """
    增强的 RAG 问答

    Args:
        query: 问题
        settings: 配置
        vector_store: 向量存储
        embedder: 嵌入管理器
        llm: LLM 实例
        top_k: 检索文档数量
        use_multi_query: 是否使用多查询检索
        use_rerank: 是否使用结果重排序

    Returns:
        RAG 结果
    """
    from .search import semantic_search

    # 1. 检索
    if use_multi_query:
        results = multi_query_search(
            query, vector_store, embedder, llm, top_k=top_k
        )
    else:
        results = semantic_search(query, vector_store, embedder, top_k=top_k)

    if not results:
        return {
            "answer": "知识库中未找到与问题相关的内容。请先导入相关文档。",
            "sources": [],
            "context": "",
            "query": query,
        }

    # 2. 重排序（可选）
    if use_rerank:
        results = rerank_results(query, results, llm, top_k=top_k)
    else:
        results = results[:top_k]

    # 3. 构建上下文
    context_parts = []
    sources = []
    for i, r in enumerate(results, 1):
        context_parts.append(f"[来源{i}] {r.title}\n{r.text}")
        sources.append({
            "index": i,
            "title": r.title,
            "source": r.source,
            "doc_type": r.doc_type,
            "score": r.score,
        })

    context = "\n\n---\n\n".join(context_parts)

    # 4. 生成回答
    system_prompt = """你是一个基于用户知识库的问答助手。根据提供的参考资料回答用户问题。

规则：
- 只基于提供的参考资料回答，不要编造信息
- 如果参考资料不足以回答问题，明确说明
- 在回答中标注信息来源（使用 [来源N] 格式）
- 使用中文回答
- 回答要准确、简洁、有条理"""

    user_prompt = f"""参考资料：

{context}

问题：{query}

请基于参考资料回答问题，并标注信息来源。"""

    answer = llm.chat(system_prompt, user_prompt)

    return {
        "answer": answer,
        "sources": sources,
        "context": context,
        "query": query,
    }
