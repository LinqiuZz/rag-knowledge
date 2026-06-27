"""企业级检索与重排序模块

流程:
  1. 查询改写（上下文补全 → 任务分解 → HyDE）
  2. 权限解析
  3. ANN 语义搜索（多查询合并去重）
  4. 混合检索增强（关键词）
  5. 父块上下文扩展
  6. Cross-Encoder 重排序
  7. 加权综合评分: final = 0.7*rerank + 0.2*freshness + 0.1*keyword
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════

@dataclass
class RetrievalHit:
    """检索命中项。"""
    chunk_id: str
    text: str
    plain_text: str
    source: str
    title: str
    doc_type: str
    doc_id: int
    version_id: int
    page_number: int = 0
    slide_number: int = 0
    element_type: str = "Paragraph"
    semantic_score: float = 0.0
    keyword_score: float = 0.0
    rerank_score: float = 0.0
    freshness_score: float = 0.0
    final_score: float = 0.0
    parent_chunk_id: str = ""
    parent_text: str = ""
    permission_ids: list[int] = field(default_factory=list)
    updated_at: str = ""


@dataclass
class RetrievalResult:
    """检索结果。"""
    query: str
    hits: list[RetrievalHit]
    rewritten_queries: list[str] = field(default_factory=list)
    total_candidates: int = 0
    filtered_count: int = 0
    reranked_count: int = 0
    final_count: int = 0


# ═══════════════════════════════════════════════════════════════
# 检索编排
# ═══════════════════════════════════════════════════════════════

class RetrievalPipeline:
    """企业级检索流水线。"""

    def __init__(self, settings, llm=None):
        from ..config import Settings
        self.settings: Settings = settings
        self.llm = llm
        self.top_k = settings.retrieval.top_k
        self.final_k = settings.retrieval.final_k
        self.w_semantic = settings.retrieval.semantic_weight
        self.w_freshness = settings.retrieval.freshness_weight
        self.w_keyword = settings.retrieval.keyword_weight
        self._rewriter = None   # 懒加载
        self._reranker = None   # 懒加载

    def retrieve(
        self,
        query: str,
        embedder,
        vector_store,
        meta_store=None,
        user_id: int = None,
        use_hybrid: bool = True,
        use_rerank: bool = True,
        expand_context: bool = True,
        use_rewrite: bool = False,
        use_hyde: bool = False,
        use_decompose: bool = True,
        use_compress: bool = True,
        history: list[dict] = None,
    ) -> RetrievalResult:
        """执行完整的检索流程。"""

        # ── Step 0: 查询改写 ──
        queries = [query]
        if use_rewrite:
            queries = self._rewrite(query, history, use_compress, use_decompose, use_hyde)

        # ── Step 1: 权限 ──
        accessible_doc_ids = _resolve_permissions(user_id, meta_store)
        if accessible_doc_ids is not None and not accessible_doc_ids:
            return RetrievalResult(query=query, rewritten_queries=queries)
        filter_expr = _build_filter(accessible_doc_ids)

        # ── Step 2: ANN 搜索（多查询合并去重）──
        all_hits: dict[str, RetrievalHit] = {}
        total_candidates = 0

        for q in queries:
            q_vec = embedder.embed_query(q)
            ann = vector_store.search(q_vec, top_k=self.top_k, filter_expr=filter_expr)
            total_candidates += len(ann.get("ids", [[]])[0])

            for hit in _parse_hits(ann):
                existing = all_hits.get(hit.chunk_id)
                if existing is None:
                    all_hits[hit.chunk_id] = hit
                elif hit.semantic_score > existing.semantic_score:
                    existing.semantic_score = hit.semantic_score

        hits = list(all_hits.values())

        # ── Step 3: 关键词增强 ──
        if use_hybrid and hits:
            _apply_keyword_scores(query, hits, vector_store, self.top_k)

        # ── Step 4: 父块上下文 ──
        if expand_context and hits and meta_store:
            _expand_parent_context(hits, meta_store)

        # ── Step 5: 重排序 ──
        if use_rerank and hits:
            self._do_rerank(query, hits)

        # ── Step 6: 加权评分 ──
        _compute_final_scores(hits, self.w_semantic, self.w_freshness, self.w_keyword)
        hits.sort(key=lambda h: h.final_score, reverse=True)
        hits = hits[:self.final_k]

        return RetrievalResult(
            query=query, hits=hits, rewritten_queries=queries,
            total_candidates=total_candidates, filtered_count=len(all_hits),
            reranked_count=len(hits), final_count=len(hits),
        )

    # ── 内部方法 ──────────────────────────────────────────────

    def _rewrite(self, query, history, use_compress, use_decompose, use_hyde):
        if self._rewriter is None:
            from .rewriting import QueryRewriter
            self._rewriter = QueryRewriter(self.settings, self.llm)

        plans = self._rewriter.rewrite(
            query, history=history,
            use_compress=use_compress, use_decompose=use_decompose, use_hyde=use_hyde,
        )
        out = [q for p in plans for q in p.queries]
        logger.info("查询改写: %r → %s", query, out)
        return out or [query]

    def _do_rerank(self, query, hits):
        if self._reranker is None:
            self._reranker = _load_reranker(self.settings)
        _apply_rerank(self._reranker, query, hits)


# ═══════════════════════════════════════════════════════════════
# 权限
# ═══════════════════════════════════════════════════════════════

def _resolve_permissions(user_id, meta_store) -> list[int] | None:
    if not user_id or not meta_store:
        return None
    try:
        return meta_store.get_accessible_doc_ids(user_id)
    except Exception as e:
        logger.warning("权限查询失败，忽略: %s", e)
        return None


def _build_filter(accessible_doc_ids):
    """构建向量数据库过滤条件。

    ChromaDB 不支持复杂标量过滤，只在 Qdrant/Milvus 上启用 is_active 过滤。
    """
    # ChromaDB 的 where 过滤能力有限，跳过 is_active 过滤
    # 旧数据没有 is_active 字段，过滤会导致 0 结果
    if accessible_doc_ids:
        return {"doc_id": accessible_doc_ids}
    return None


# ═══════════════════════════════════════════════════════════════
# 结果解析
# ═══════════════════════════════════════════════════════════════

def _parse_hits(ann_results) -> list[RetrievalHit]:
    hits = []
    docs = ann_results.get("documents", [[]])[0]
    metas = ann_results.get("metadatas", [[]])[0]
    dists = ann_results.get("distances", [[]])[0]

    for text, meta, dist in zip(docs, metas, dists):
        if not text:
            continue
        hits.append(RetrievalHit(
            chunk_id=meta.get("chunk_id", ""),
            text=text,
            plain_text=meta.get("plain_text", text),
            source=meta.get("source", ""),
            title=meta.get("title", ""),
            doc_type=meta.get("doc_type", ""),
            doc_id=int(meta.get("doc_id", 0)),
            version_id=int(meta.get("version_id", 0)),
            page_number=int(meta.get("page_number", 0)),
            slide_number=int(meta.get("slide_number", 0)),
            element_type=meta.get("element_type", "Paragraph"),
            semantic_score=max(0.0, 1.0 - float(dist)) if dist else 0.0,
            parent_chunk_id=meta.get("parent_chunk_id", ""),
            updated_at=meta.get("updated_at", ""),
        ))
    return hits


# ═══════════════════════════════════════════════════════════════
# 关键词匹配（只在已有 hits 范围内评分，不加载全库）
# ═══════════════════════════════════════════════════════════════

def _apply_keyword_scores(query, hits, vector_store, top_k):
    """为已有 hits 计算关键词命中率。"""
    query_keywords = set(query.lower().split())
    if not query_keywords:
        return

    for hit in hits:
        text_lower = hit.plain_text.lower()
        hit.keyword_score = sum(1 for kw in query_keywords if kw in text_lower) / len(query_keywords)


# ═══════════════════════════════════════════════════════════════
# 父块上下文扩展
# ═══════════════════════════════════════════════════════════════

def _expand_parent_context(hits, meta_store):
    parent_ids = list({h.parent_chunk_id for h in hits if h.parent_chunk_id})
    if not parent_ids:
        return
    try:
        cur = meta_store.conn.cursor()
        placeholders = ", ".join(["%s"] * len(parent_ids))
        cur.execute(
            f"SELECT chunk_id, text FROM document_chunks WHERE chunk_id IN ({placeholders})",
            parent_ids,
        )
        parent_map = {row[0]: row[1] for row in cur.fetchall()}
        cur.close()
        for hit in hits:
            if hit.parent_chunk_id in parent_map:
                hit.parent_text = parent_map[hit.parent_chunk_id]
    except Exception as e:
        logger.warning("父块扩展失败: %s", e)


# ═══════════════════════════════════════════════════════════════
# 重排序
# ═══════════════════════════════════════════════════════════════

def _load_reranker(settings):
    model_name = settings.retrieval.rerank_model
    if not model_name:
        logger.info("重排序模型未配置，跳过")
        return None
    try:
        from sentence_transformers import CrossEncoder
        logger.info("加载重排序模型: %s", model_name)
        return CrossEncoder(model_name, max_length=512, device=settings.embedding.device)
    except ImportError:
        logger.warning("sentence-transformers 未安装，重排序不可用")
        return None
    except Exception as e:
        logger.warning("重排序模型加载失败: %s", e)
        return None


def _apply_rerank(model, query, hits):
    """对 hits 应用重排序 + 新鲜度。"""
    if model is None or not hits:
        for h in hits:
            h.rerank_score = h.semantic_score
            h.freshness_score = _calc_freshness(h.updated_at)
        return

    try:
        pairs = [(query, h.plain_text[:2000]) for h in hits]
        scores = model.predict(pairs, show_progress_bar=False)

        if len(scores) > 1:
            lo, hi = scores.min(), scores.max()
            scores = (scores - lo) / (hi - lo) if hi > lo else scores * 0 + 0.5
        else:
            scores = [1.0]

        for hit, score in zip(hits, scores):
            hit.rerank_score = float(score)
            hit.freshness_score = _calc_freshness(hit.updated_at)
    except Exception as e:
        logger.warning("重排序失败: %s，回退到语义分数", e)
        for h in hits:
            h.rerank_score = h.semantic_score
            h.freshness_score = _calc_freshness(h.updated_at)


def _calc_freshness(updated_at: str) -> float:
    if not updated_at:
        return 0.5
    try:
        if isinstance(updated_at, str):
            dt = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
        else:
            dt = updated_at
        return max(0.0, 1.0 - (datetime.now(timezone.utc) - dt).days / 365.0)
    except Exception:
        return 0.5


# ═══════════════════════════════════════════════════════════════
# 加权评分
# ═══════════════════════════════════════════════════════════════

def _compute_final_scores(hits, w_sem, w_fresh, w_kw):
    for h in hits:
        h.final_score = w_sem * h.rerank_score + w_fresh * h.freshness_score + w_kw * h.keyword_score


# ═══════════════════════════════════════════════════════════════
# 构建 RAG 上下文
# ═══════════════════════════════════════════════════════════════

def build_rag_context(hits: list[RetrievalHit], include_parents: bool = True):
    """从检索命中构建 LLM 上下文和来源列表。

    Returns:
        (context_text, sources)
    """
    context_parts = []
    sources = []

    for i, hit in enumerate(hits, 1):
        location = ""
        if hit.page_number:
            location = f"第{hit.page_number}页"
        elif hit.slide_number:
            location = f"幻灯片{hit.slide_number}"

        header = f"[{i}] 文档《{hit.title}》{location}"
        if hit.element_type.startswith("Heading"):
            header += f" [{hit.element_type}]"

        content = hit.plain_text
        if include_parents and hit.parent_text:
            content = f"{hit.plain_text}\n---\n上下文：{hit.parent_text}"

        context_parts.append(f"{header}：\n{content}")
        sources.append({
            "index": i, "title": hit.title, "source": hit.source,
            "doc_type": hit.doc_type, "page_number": hit.page_number,
            "slide_number": hit.slide_number, "element_type": hit.element_type,
            "score": hit.final_score, "chunk_id": hit.chunk_id,
        })

    return "\n\n---\n\n".join(context_parts), sources
