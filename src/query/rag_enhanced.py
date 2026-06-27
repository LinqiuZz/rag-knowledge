"""增强 RAG — 已合并到 rag.py + retrieval.py

本模块保留为向后兼容的桥接层。
多查询检索和重排序功能已整合到:
  - src/query/retrieval.py  (RetrievalPipeline)
  - src/query/rag.py        (rag_answer)
"""

from .rag import rag_answer

# ── 向后兼容重导出 ────────────────────────────────────────────────
from .retrieval import RetrievalPipeline

def multi_query_search(query, vector_store, embedder, llm=None, top_k=5, num_queries=3):
    """多查询检索 — 兼容旧接口，委托给 RetrievalPipeline。"""
    from .search import semantic_search

    all_results = semantic_search(query, vector_store, embedder, top_k=top_k)
    if llm is None:
        return all_results

    query_gen_prompt = (
        f"请根据以下查询生成 {num_queries} 个相关但不同角度的查询。\n"
        f"原始查询: {query}\n"
        f'请用 JSON 格式回复: {{"queries": ["查询1", "查询2"]}}'
    )
    try:
        import json
        response = llm.chat("你是查询扩展专家。", query_gen_prompt)
        queries = json.loads(response).get("queries", [])
    except Exception:
        queries = []

    seen_sources = {r.source for r in all_results}
    for expanded_query in queries[:num_queries]:
        results = semantic_search(expanded_query, vector_store, embedder, top_k=top_k)
        for r in results:
            if r.source not in seen_sources:
                all_results.append(r)
                seen_sources.add(r.source)

    return all_results


def rerank_results(query, results, llm=None, top_k=5):
    """LLM 重排序 — 兼容旧接口。"""
    if llm is None or len(results) <= top_k:
        return results[:top_k]

    docs_text = "\n\n".join(
        f"[文档{i+1}] {r.title}\n{r.text[:200]}..."
        for i, r in enumerate(results[:10])
    )
    rerank_prompt = (
        f"请根据查询对以下文档进行相关性排序。\n"
        f"查询: {query}\n\n文档列表:\n{docs_text}\n\n"
        f'请返回最相关 {top_k} 个文档编号 (JSON): {{"ranked_indices": [1, 3, 5]}}'
    )
    try:
        import json
        response = llm.chat("你是文档排序专家。", rerank_prompt)
        ranked = json.loads(response).get("ranked_indices", [])
        return [results[idx - 1] for idx in ranked[:top_k] if 1 <= idx <= len(results)]
    except Exception:
        return results[:top_k]


def enhanced_rag_answer(query, settings, vector_store, embedder, llm,
                        top_k=5, use_multi_query=False, use_rerank=False):
    """增强 RAG — 兼容旧接口，委托给 rag_answer。"""
    return rag_answer(
        question=query, settings=settings,
        vector_store=vector_store, embedder=embedder, llm=llm,
        top_k=top_k, use_multi_query=use_multi_query, use_rerank=use_rerank,
    )


__all__ = [
    "rag_answer",
    "multi_query_search",
    "rerank_results",
    "enhanced_rag_answer",
    "RetrievalPipeline",
]
