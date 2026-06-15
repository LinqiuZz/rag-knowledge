"""API 路由定义"""

from __future__ import annotations

import re
import hashlib
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional
from pathlib import Path

from ..config import load_settings
from ..store.vector import VectorStore
from ..store.metadata import MetadataStore
from ..store.embedding import EmbeddingManager
from ..llm.base import get_llm

from .schemas import (
    SearchRequest, SearchResponse, SearchResultItem,
    RAGRequest, RAGResponse, RAGSource,
    IngestResponse, SummarizeRequest, SummarizeResponse,
    DocumentInfo, SystemInfo, ErrorResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ── 全局组件（应用启动时初始化，避免每次请求重建） ─────────────
_components = None


def _get_components():
    """获取全局组件（懒加载，首次调用时初始化）"""
    global _components
    if _components is None:
        settings = load_settings()
        embedder = EmbeddingManager(settings)
        vector_store = VectorStore(settings)
        meta_store = MetadataStore(settings)
        llm = get_llm(settings.llm.default, settings)
        _components = (settings, embedder, vector_store, meta_store, llm)
    return _components


def _sanitize_filename(filename: str) -> str:
    """清洗文件名，防止路径遍历攻击"""
    # 只取文件名部分，去除路径
    name = Path(filename).name
    # 移除危险字符
    name = re.sub(r'[^\w\s\-\.]', '', name)
    # 确保不为空
    if not name or name.startswith('.'):
        name = f"file_{hashlib.md5(filename.encode()).hexdigest()[:8]}"
    return name


# ── 搜索 ──────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse, tags=["查询"])
async def search(request: SearchRequest):
    """语义搜索知识库"""
    try:
        _, embedder, vs, _, _ = _get_components()
        
        from ..query.search import semantic_search
        results = semantic_search(request.query, vs, embedder, top_k=request.top_k)
        
        items = [
            SearchResultItem(
                text=r.text,
                source=r.source,
                title=r.title,
                doc_type=r.doc_type,
                score=1 - r.score,  # 转换为相似度（越大越相似）
                chunk_idx=r.chunk_idx,
            )
            for r in results
        ]
        
        return SearchResponse(results=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── RAG 问答 ──────────────────────────────────────────────

@router.post("/ask", response_model=RAGResponse, tags=["查询"])
async def ask(request: RAGRequest):
    """RAG 问答 — 基于知识库回答问题"""
    try:
        settings, embedder, vs, _, llm = _get_components()
        
        if request.llm_backend:
            settings.llm.default = request.llm_backend
            llm = get_llm(request.llm_backend, settings)
        
        if not llm.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"LLM 后端 ({settings.llm.default}) 不可用"
            )
        
        from ..query.rag import rag_answer
        result = rag_answer(request.question, settings, vs, embedder, llm, top_k=request.top_k)
        
        sources = [
            RAGSource(
                index=s["index"],
                title=s["title"],
                source=s["source"],
                doc_type=s["doc_type"],
                score=1 - s["score"],
            )
            for s in result["sources"]
        ]
        
        return RAGResponse(answer=result["answer"], sources=sources)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 文档导入 ──────────────────────────────────────────────

@router.post("/ingest/pdf", response_model=IngestResponse, tags=["摄取"])
async def ingest_pdf(file: UploadFile = File(...)):
    """导入 PDF 文件到知识库"""
    try:
        settings, embedder, vs, ms, _ = _get_components()

        # 清洗文件名，防止路径遍历
        safe_name = _sanitize_filename(file.filename)
        if not safe_name.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

        # 保存上传的文件到临时位置
        temp_path = Path(settings.raw_dir) / "temp" / safe_name
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        from ..ingest.pipeline import ingest_pdf as do_ingest
        result = do_ingest(str(temp_path), settings, vs, ms, embedder)

        return IngestResponse(
            title=result["title"],
            chunk_count=result["chunk_count"],
            char_count=result["char_count"],
            doc_type="pdf",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"导入PDF失败: {e}")
        raise HTTPException(status_code=500, detail="导入PDF失败")


# ── 文档摘要 ──────────────────────────────────────────────

@router.post("/summarize", response_model=SummarizeResponse, tags=["查询"])
async def summarize(request: SummarizeRequest):
    """为已导入的文档生成摘要"""
    try:
        settings, embedder, vs, ms, llm = _get_components()
        
        if request.llm_backend:
            settings.llm.default = request.llm_backend
            llm = get_llm(request.llm_backend, settings)
        
        if not llm.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"LLM 后端 ({settings.llm.default}) 不可用"
            )
        
        from ..query.summarize import summarize_document
        summary = summarize_document(request.source, settings, vs, ms, embedder, llm)
        
        return SummarizeResponse(source=request.source, summary=summary)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 文档列表 ──────────────────────────────────────────────

@router.get("/documents", response_model=list[DocumentInfo], tags=["管理"])
async def list_documents():
    """列出知识库中的所有文档"""
    try:
        _, _, vs, ms, _ = _get_components()
        docs = ms.list_documents()
        
        return [
            DocumentInfo(
                title=doc["title"],
                doc_type=doc["doc_type"],
                chunk_count=doc["chunk_count"],
                char_count=doc["char_count"],
                created_at=doc["created_at"],
            )
            for doc in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 文档删除 ──────────────────────────────────────────────

@router.delete("/documents/{source:path}", tags=["管理"])
async def delete_document(source: str):
    """从知识库删除指定文档"""
    try:
        _, _, vs, ms, _ = _get_components()

        count = vs.delete_by_source(source)
        ms.delete_document(source)

        return {"message": f"已删除 {count} 个向量块", "source": source}
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail="删除文档失败")


# ── 系统信息 ──────────────────────────────────────────────

@router.get("/info", response_model=SystemInfo, tags=["系统"])
async def get_info():
    """获取系统状态和配置信息"""
    try:
        settings, _, vs, ms, _ = _get_components()
        docs = ms.list_documents()
        
        return SystemInfo(
            llm_backend=settings.llm.default,
            embedding_model=settings.embedding.model_name,
            document_count=len(docs),
            total_chunks=vs.count(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 增强 RAG 问答 ──────────────────────────────────────────

@router.post("/ask/enhanced", response_model=RAGResponse, tags=["查询"])
async def ask_enhanced(
    question: str,
    top_k: int = 5,
    use_multi_query: bool = False,
    use_rerank: bool = False,
    llm_backend: Optional[str] = None,
):
    """增强的 RAG 问答（支持多查询和重排序）"""
    try:
        settings, embedder, vs, _, llm = _get_components()
        
        if llm_backend:
            settings.llm.default = llm_backend
            llm = get_llm(llm_backend, settings)
        
        if not llm.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"LLM 后端 ({settings.llm.default}) 不可用"
            )
        
        from ..query.rag_enhanced import enhanced_rag_answer
        result = enhanced_rag_answer(
            question, settings, vs, embedder, llm,
            top_k=top_k,
            use_multi_query=use_multi_query,
            use_rerank=use_rerank,
        )
        
        sources = [
            RAGSource(
                index=s["index"],
                title=s["title"],
                source=s["source"],
                doc_type=s["doc_type"],
                score=1 - s["score"],
            )
            for s in result["sources"]
        ]
        
        return RAGResponse(answer=result["answer"], sources=sources)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── RAG 评估 ──────────────────────────────────────────────

class RAGEvalRequest(BaseModel):
    """RAG 评估请求"""
    query: str = Field(..., description="查询")
    top_k: int = Field(5, ge=1, le=20, description="检索文档数量")
    llm_backend: Optional[str] = Field(None, description="LLM 后端")

class RAGEvalResponse(BaseModel):
    """RAG 评估响应"""
    query: str = Field(..., description="查询")
    answer: str = Field(..., description="生成的回答")
    metrics: dict = Field(..., description="评估指标")

@router.post("/evaluate", response_model=RAGEvalResponse, tags=["评估"])
async def evaluate_rag(request: RAGEvalRequest):
    """评估 RAG 问答质量"""
    try:
        settings, embedder, vs, _, llm = _get_components()
        
        if request.llm_backend:
            settings.llm.default = request.llm_backend
            llm = get_llm(request.llm_backend, settings)
        
        if not llm.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"LLM 后端 ({settings.llm.default}) 不可用"
            )
        
        from ..query.rag import rag_answer
        from ..query.evaluation import rag_evaluate
        
        # 执行 RAG 问答
        result = rag_answer(request.query, settings, vs, embedder, llm, top_k=request.top_k)
        
        # 评估结果
        context = "\n\n".join([s.get("title", "") for s in result["sources"]])
        evaluation = rag_evaluate(
            request.query,
            result["answer"],
            result["sources"],
            context,
            llm=llm,
            k=request.top_k,
        )
        
        return RAGEvalResponse(
            query=request.query,
            answer=result["answer"],
            metrics=evaluation.metrics,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 混合检索 ──────────────────────────────────────────────

@router.post("/search/hybrid", response_model=SearchResponse, tags=["查询"])
async def hybrid_search_endpoint(
    query: str,
    top_k: int = 5,
    semantic_weight: float = 0.7,
    keyword_weight: float = 0.3,
):
    """混合检索（语义 + 关键词）"""
    try:
        _, embedder, vs, _, _ = _get_components()

        from ..query.hybrid_search import hybrid_search
        results = hybrid_search(
            query, vs, embedder,
            top_k=top_k,
            semantic_weight=semantic_weight,
            keyword_weight=keyword_weight,
        )

        items = [
            SearchResultItem(
                text=r.text,
                source=r.source,
                title=r.title,
                doc_type=r.doc_type,
                score=r.combined_score,
                chunk_idx=r.chunk_idx,
            )
            for r in results
        ]

        return SearchResponse(results=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 多轮对话 ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = Field(None, description="会话 ID（为空则创建新会话）")
    top_k: int = Field(5, ge=1, le=20, description="检索文档数量")
    llm_backend: Optional[str] = Field(None, description="LLM 后端")

class ChatResponse(BaseModel):
    """对话响应"""
    answer: str = Field(..., description="回答")
    sources: list[RAGSource] = Field(..., description="引用来源")
    session_id: str = Field(..., description="会话 ID")
    message_count: int = Field(..., description="消息总数")

# 全局对话记忆管理器
_conversation_memory = None

def _get_memory():
    """获取对话记忆管理器"""
    global _conversation_memory
    if _conversation_memory is None:
        from ..query.memory import ConversationMemory
        _conversation_memory = ConversationMemory()
    return _conversation_memory

@router.post("/chat", response_model=ChatResponse, tags=["对话"])
async def chat(request: ChatRequest):
    """多轮对话 RAG"""
    try:
        settings, embedder, vs, _, llm = _get_components()

        if request.llm_backend:
            settings.llm.default = request.llm_backend
            llm = get_llm(request.llm_backend, settings)

        if not llm.is_available():
            raise HTTPException(
                status_code=503,
                detail=f"LLM 后端 ({settings.llm.default}) 不可用"
            )

        # 获取或创建会话
        memory = _get_memory()
        session = memory.get_session(request.session_id)
        if session is None:
            session = memory.create_session(request.session_id)

        from ..query.memory import multi_turn_rag
        result = multi_turn_rag(
            request.message, session, settings, vs, embedder, llm,
            top_k=request.top_k,
        )

        sources = [
            RAGSource(
                index=s["index"],
                title=s["title"],
                source=s["source"],
                doc_type=s["doc_type"],
                score=1 - s["score"],
            )
            for s in result["sources"]
        ]

        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            session_id=result["session_id"],
            message_count=result["message_count"],
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 多格式文档导入 ────────────────────────────────────────

@router.post("/ingest/document", response_model=IngestResponse, tags=["摄取"])
async def ingest_document(file: UploadFile = File(...)):
    """导入多格式文档（PDF、Word、Excel、Markdown、TXT、HTML）"""
    try:
        settings, embedder, vs, ms, _ = _get_components()

        # 检查文件格式
        allowed_formats = [".pdf", ".docx", ".xlsx", ".xls", ".md", ".txt", ".html", ".htm"]
        suffix = Path(file.filename).suffix.lower()
        if suffix not in allowed_formats:
            if suffix == ".doc":
                raise HTTPException(
                    status_code=400,
                    detail="不支持旧版 .doc 格式，请转换为 .docx 格式后重试"
                )
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {suffix}，支持: {', '.join(allowed_formats)}"
            )

        # 清洗文件名，防止路径遍历
        safe_name = _sanitize_filename(file.filename)

        # 保存上传的文件
        temp_path = Path(settings.raw_dir) / "temp" / safe_name
        temp_path.parent.mkdir(parents=True, exist_ok=True)

        with open(temp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # 解析文档
        from ..ingest.parsers import parse_document
        doc = parse_document(str(temp_path))

        # 分块
        from ..ingest.chunking import split_text
        chunks = split_text(doc.text, settings.chunking.size, settings.chunking.overlap)

        # 生成嵌入
        embeddings = embedder.embed(chunks)

        # 存储
        import hashlib
        source = str(temp_path.resolve())
        ids = [hashlib.md5(f"{source}_{i}".encode()).hexdigest()[:12] for i in range(len(chunks))]
        metadatas = [
            {
                "source": source,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "chunk_idx": i,
            }
            for i in range(len(chunks))
        ]

        vs.add(ids, chunks, embeddings, metadatas)
        ms.add_document(source, doc.title, doc.doc_type, len(chunks), doc.char_count)

        return IngestResponse(
            title=doc.title,
            chunk_count=len(chunks),
            char_count=doc.char_count,
            doc_type=doc.doc_type,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
