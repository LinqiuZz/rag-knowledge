"""RAG 问答 — 企业版

查询改写 → 检索 → 重排序 → 扩展上下文 → 生成回答
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Settings
    from ..store.vector import BaseVectorStore
    from ..store.embedding import EmbeddingManager
    from ..store.metadata import MetadataStore
    from ..llm.base import BaseLLM

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个企业知识库助手。请严格按照以下规则回答：

1. **准确性优先**：只基于提供的参考资料回答，绝不编造信息
2. **来源标注**：每个关键信息点必须标注来源 [来源N]
3. **结构化回答**：使用标题、列表、代码块等结构化格式
4. **完整性检查**：如果参考资料不足，明确说明"根据现有资料无法完整回答"
5. **专业术语**：保持技术术语的准确性，必要时给出解释

回答风格：专业、准确、有条理、易于理解"""

_EMPTY_RESULT = {
    "answer": "知识库中未找到与问题相关的内容。请先导入相关文档。",
    "sources": [],
    "context": "",
    "query": "",
    "rewritten_queries": [],
}


def rag_answer(
    question: str,
    settings: Settings,
    vector_store: BaseVectorStore,
    embedder: EmbeddingManager,
    llm: BaseLLM,
    meta_store: MetadataStore = None,
    top_k: int = 5,
    use_hybrid: bool = False,
    use_multi_query: bool = False,
    use_rerank: bool = True,
    user_id: int = None,
    use_rewrite: bool = True,
    use_hyde: bool = True,
    use_decompose: bool = True,
    use_compress: bool = True,
    history: list[dict] = None,
    pipeline=None,
) -> dict:
    """
    RAG 问答：查询改写 → 检索 → 重排序 → 生成回答。

    Returns:
        {answer, sources, context, query, rewritten_queries}
    """
    from .retrieval import RetrievalPipeline, build_rag_context

    if pipeline is None:
        pipeline = RetrievalPipeline(settings, llm=llm)
    result = pipeline.retrieve(
        query=question, embedder=embedder, vector_store=vector_store,
        meta_store=meta_store, user_id=user_id,
        use_hybrid=use_hybrid, use_rerank=use_rerank,
        use_rewrite=use_rewrite, use_hyde=use_hyde,
        use_decompose=use_decompose, use_compress=use_compress,
        history=history,
    )

    if not result.hits:
        return {**_EMPTY_RESULT, "query": question, "rewritten_queries": [question]}

    hits = result.hits[:top_k]
    context, sources = build_rag_context(hits)

    answer = llm.chat(SYSTEM_PROMPT, _build_user_prompt(question, context))

    return {
        "answer": answer,
        "sources": sources,
        "context": context,
        "query": question,
        "rewritten_queries": result.rewritten_queries,
    }


def _build_user_prompt(question: str, context: str) -> str:
    return (
        f"参考资料：\n\n{context}\n\n"
        f"问题：{question}\n\n"
        f"请基于参考资料回答问题，并在回答中标注来源编号。"
    )
