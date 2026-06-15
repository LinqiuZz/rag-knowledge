"""文档摘要生成"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .search import semantic_search

if TYPE_CHECKING:
    from ..config import Settings
    from ..store.vector import VectorStore
    from ..store.metadata import MetadataStore
    from ..store.embedding import EmbeddingManager
    from ..llm.base import BaseLLM


SYSTEM_PROMPT = """你是一个专业的文档分析助手。请根据提供的文档内容生成简洁、准确的摘要。
要求：
- 使用中文
- 保留关键信息和核心观点
- 结构清晰，使用要点列举
- 如果内容不足以生成有意义的摘要，如实说明"""


def summarize_document(
    source: str,
    settings: Settings,
    vector_store: VectorStore,
    meta_store: MetadataStore,
    embedder: EmbeddingManager,
    llm: BaseLLM,
    max_chunks: int = 20,
) -> str:
    """
    对已入库的文档生成摘要。

    通过 source (文件路径或 URL) 查找所有相关块，
    拼接后调用 LLM 生成摘要。超长文档取前 max_chunks 块。
    """
    # 从向量库中取出来自该 source 的块
    all_meta = vector_store.collection.get(
        where={"source": source},
        include=["documents", "metadatas"],
    )

    if not all_meta["ids"]:
        return f"未找到来源为 {source} 的文档块。"

    # 按 chunk_idx 排序
    pairs = list(zip(
        all_meta["documents"],
        [m.get("chunk_idx", 0) for m in all_meta["metadatas"]],
    ))
    pairs.sort(key=lambda x: x[1])
    texts = [p[0] for p in pairs]

    if len(texts) > max_chunks:
        texts = texts[:max_chunks]

    content = "\n\n---\n\n".join(texts)

    user_prompt = f"请为以下文档生成摘要：\n\n{content}"
    return llm.chat(SYSTEM_PROMPT, user_prompt)


def summarize_query(
    query: str,
    settings: Settings,
    vector_store: VectorStore,
    embedder: EmbeddingManager,
    llm: BaseLLM,
    top_k: int = 10,
) -> str:
    """
    基于查询的摘要：搜索相关内容后综合生成摘要。
    """
    results = semantic_search(query, vector_store, embedder, top_k=top_k)

    if not results:
        return "未找到与查询相关的内容。"

    content = "\n\n---\n\n".join(
        f"[来源: {r.title}]\n{r.text}" for r in results
    )

    user_prompt = (
        f"用户查询：{query}\n\n"
        f"以下是与查询相关的文档片段，请综合这些内容生成一份摘要回答：\n\n{content}"
    )
    return llm.chat(SYSTEM_PROMPT, user_prompt)
