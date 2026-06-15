"""RAG 问答"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .search import semantic_search
from .hybrid_search import hybrid_search
from .rag_enhanced import multi_query_search

if TYPE_CHECKING:
    from ..config import Settings
    from ..store.vector import VectorStore
    from ..store.embedding import EmbeddingManager
    from ..llm.base import BaseLLM


SYSTEM_PROMPT = """你是一个专业的技术问答助手。请严格按照以下规则回答：

1. **准确性优先**：只基于提供的参考资料回答，绝不编造信息
2. **来源标注**：每个关键信息点必须标注来源 [来源N]
3. **结构化回答**：使用标题、列表、代码块等结构化格式
4. **完整性检查**：如果参考资料不足，明确说明"根据现有资料无法完整回答"
5. **专业术语**：保持技术术语的准确性，必要时给出解释

回答风格：专业、准确、有条理、易于理解"""


def rag_answer(
    question: str,
    settings: Settings,
    vector_store: VectorStore,
    embedder: EmbeddingManager,
    llm: BaseLLM,
    top_k: int = 5,
    use_hybrid: bool = False,
    use_multi_query: bool = False,
) -> dict:
    """
    RAG 问答：检索相关文档 → 构建上下文 → 生成回答。

    Args:
        question: 用户问题
        settings: 配置对象
        vector_store: 向量存储
        embedder: 嵌入管理器
        llm: LLM实例
        top_k: 检索文档数量
        use_hybrid: 是否使用混合检索
        use_multi_query: 是否使用多查询检索

    Returns:
        {
            "answer": str,          # 生成的回答
            "sources": list[dict],  # 引用的来源
            "context": str,         # 检索到的上下文
            "query": str,           # 原始查询
        }
    """
    # 1. 检索策略选择
    if use_multi_query:
        # 使用多查询检索（提高召回率）
        results = multi_query_search(
            question, vector_store, embedder, llm, top_k=top_k
        )
    elif use_hybrid:
        # 使用混合检索（语义 + 关键词）
        hybrid_results = hybrid_search(
            question, vector_store, embedder, top_k=top_k
        )
        # 转换为统一格式
        results = []
        for r in hybrid_results:
            # 创建一个模拟的语义搜索结果对象
            class HybridResult:
                def __init__(self, text, source, title, doc_type, score, chunk_idx):
                    self.text = text
                    self.source = source
                    self.title = title
                    self.doc_type = doc_type
                    self.score = score
                    self.chunk_idx = chunk_idx

            results.append(HybridResult(
                text=r.text,
                source=r.source,
                title=r.title,
                doc_type=r.doc_type,
                score=1 - r.combined_score,  # 转换为距离分数
                chunk_idx=r.chunk_idx
            ))
    else:
        # 使用纯语义检索
        results = semantic_search(question, vector_store, embedder, top_k=top_k)

    if not results:
        return {
            "answer": "知识库中未找到与问题相关的内容。请先导入相关文档。",
            "sources": [],
            "context": "",
            "query": question,
        }

    # 2. 构建上下文
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

    user_prompt = (
        f"参考资料：\n\n{context}\n\n"
        f"问题：{question}\n\n"
        f"请基于参考资料回答问题，并在回答中标注来源编号。"
    )

    # 3. 生成回答
    answer = llm.chat(SYSTEM_PROMPT, user_prompt)

    return {
        "answer": answer,
        "sources": sources,
        "context": context,
        "query": question,
    }
