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

# ── Few-Shot 示例 ────────────────────────────────────────────────
FEW_SHOT_EXAMPLES = """【示例】
用户问题：什么是向量数据库？它和传统数据库有什么区别？
参考资料：
[来源1] 向量数据库是专门用于存储和检索高维向量的数据库系统，通过近似最近邻（ANN）算法实现高效的语义相似度搜索。常见实现包括 Milvus、Qdrant、ChromaDB 等。
[来源2] 传统关系型数据库基于行和列存储结构化数据，使用 SQL 进行精确匹配查询，适合事务处理和结构化数据分析。

回答：
## 向量数据库概述
向量数据库是专门用于存储和检索高维向量的数据库系统[来源1]，通过近似最近邻（ANN）算法实现高效的语义相似度搜索[来源1]。
## 与传统数据库的区别
- **数据模型**：传统关系型数据库基于行和列存储结构化数据[来源2]，而向量数据库存储高维嵌入向量[来源1]
- **查询方式**：传统数据库使用精确匹配查询[来源2]，向量数据库使用相似度搜索[来源1]
- **适用场景**：传统数据库适合事务处理，向量数据库适合语义检索和推荐系统[来源1][来源2]
"""

# ── CoT 后缀 ─────────────────────────────────────────────────────
COT_SUFFIX = (
    "\n\n请按以下步骤回答：\n"
    "1. 先从参考资料中提取与问题相关的关键信息\n"
    "2. 逐步分析和推理\n"
    "3. 给出最终结论"
)

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
    use_few_shot: bool = True,
    use_cot: bool = True,
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

    sys_prompt = SYSTEM_PROMPT
    if use_cot:
        sys_prompt += COT_SUFFIX

    answer = llm.chat(sys_prompt, _build_user_prompt(question, context, use_few_shot))

    return {
        "answer": answer,
        "sources": sources,
        "context": context,
        "query": question,
        "rewritten_queries": result.rewritten_queries,
    }


def _build_user_prompt(question: str, context: str, use_few_shot: bool = True) -> str:
    parts = []
    if use_few_shot:
        parts.append(FEW_SHOT_EXAMPLES.strip())
    parts.append(f"参考资料：\n\n{context}\n\n")
    parts.append(f"问题：{question}\n\n")
    parts.append("请基于参考资料回答问题，并在回答中标注来源编号。")
    return "\n".join(parts)
