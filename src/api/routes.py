"""API 路由定义 — 企业版 v2.0

主要端点:
  POST /api/search              — 语义/混合检索
  POST /api/ask                 — RAG 问答
  POST /api/chat                — 多轮对话
  POST /api/ingest/document     — 多格式文档导入
  GET  /api/documents           — 文档列表
  DELETE /api/documents/{id}    — 删除文档
  GET  /api/documents/{id}/versions — 版本历史
  POST /api/templates/upload    — 上传模板
  POST /api/generate            — 文档生成
  POST /api/permissions         — 设置权限
  GET  /api/info                — 系统信息
"""

from __future__ import annotations

import re
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

from ..bootstrap import bootstrap, AppContext
from .schemas import (
    SearchRequest, SearchResponse, SearchResultItem,
    RAGRequest, RAGResponse, RAGSource,
    IngestResponse, SummarizeRequest, SummarizeResponse,
    DocumentInfo, DocumentVersion, SystemInfo, ErrorResponse,
    TemplateUploadResponse, GenerationRequest, GenerationResponse,
    PermissionRequest,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ── 全局上下文 ──────────────────────────────────────────────────
_app: AppContext | None = None


def _get_app() -> AppContext:
    global _app
    if _app is None:
        _app = bootstrap()
    return _app


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    name = re.sub(r'[^\w\s\-\.]', '', name)
    if not name or name.startswith('.'):
        name = f"file_{hashlib.md5(filename.encode()).hexdigest()[:8]}"
    return name


# ═══════════════════════════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════════════════════════

@router.post("/search", response_model=SearchResponse, tags=["查询"])
async def search(request: SearchRequest):
    """语义/混合检索知识库"""
    try:
        app = _get_app()

        result = app.pipeline.retrieve(
            query=request.query, embedder=app.embedder,
            vector_store=app.vector_store, meta_store=app.meta_store,
            user_id=request.user_id, use_hybrid=request.use_hybrid, use_rerank=True,
        )

        items = [
            SearchResultItem(
                text=h.plain_text, source=h.source, title=h.title,
                doc_type=h.doc_type, doc_id=h.doc_id, score=h.final_score,
                page_number=h.page_number, slide_number=h.slide_number,
                element_type=h.element_type,
            )
            for h in result.hits[:request.top_k]
        ]
        return SearchResponse(results=items, total=len(items), retrieval_stats={
            "total_candidates": result.total_candidates,
            "filtered_count": result.filtered_count,
            "reranked_count": result.reranked_count,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/hybrid", response_model=SearchResponse, tags=["查询"])
async def hybrid_search_endpoint(
    query: str, top_k: int = 5, semantic_weight: float = 0.7,
    keyword_weight: float = 0.3, user_id: Optional[int] = None,
):
    """混合检索（语义 + 关键词）"""
    try:
        app = _get_app()
        from ..query.hybrid_search import hybrid_search

        results = hybrid_search(query, app.vector_store, app.embedder,
                                top_k=top_k, semantic_weight=semantic_weight,
                                keyword_weight=keyword_weight)
        items = [
            SearchResultItem(text=r.text, source=r.source, title=r.title,
                             doc_type=r.doc_type, score=r.combined_score, chunk_idx=r.chunk_idx)
            for r in results
        ]
        return SearchResponse(results=items, total=len(items))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# RAG 问答
# ═══════════════════════════════════════════════════════════════

@router.post("/ask", response_model=RAGResponse, tags=["查询"])
async def ask(request: RAGRequest):
    """RAG 问答 — 基于知识库回答问题"""
    try:
        app = _get_app()
        if request.llm_backend:
            app = bootstrap(llm_backend=request.llm_backend)

        if not app.llm.is_available():
            raise HTTPException(status_code=503,
                                detail=f"LLM 后端 ({app.settings.llm.default}) 不可用")

        from ..query.rag import rag_answer
        result = rag_answer(
            request.question, app.settings, app.vector_store, app.embedder, app.llm,
            meta_store=app.meta_store, top_k=request.top_k,
            use_hybrid=request.use_hybrid, use_multi_query=request.use_multi_query,
            use_rerank=request.use_rerank, user_id=request.user_id,
            use_rewrite=request.use_rewrite, use_hyde=request.use_hyde,
            use_decompose=request.use_decompose, use_compress=request.use_compress,
            history=request.history, pipeline=app.pipeline,
            use_few_shot=request.use_few_shot, use_cot=request.use_cot,
        )

        sources = [
            RAGSource(index=s["index"], title=s["title"], source=s["source"],
                      doc_type=s["doc_type"], score=s["score"],
                      page_number=s.get("page_number", 0),
                      slide_number=s.get("slide_number", 0),
                      element_type=s.get("element_type", "Paragraph"),
                      chunk_id=s.get("chunk_id", ""))
            for s in result["sources"]
        ]
        return RAGResponse(answer=result["answer"], sources=sources)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ask/enhanced", response_model=RAGResponse, tags=["查询"])
async def ask_enhanced(
    question: str, top_k: int = 5, use_multi_query: bool = False,
    use_rerank: bool = True, use_hybrid: bool = False,
    llm_backend: Optional[str] = None, user_id: Optional[int] = None,
    use_rewrite: bool = True, use_hyde: bool = True,
    use_decompose: bool = True, use_compress: bool = True,
    use_few_shot: bool = True, use_cot: bool = True,
):
    """增强 RAG 问答（支持查询改写：HyDE / 任务分解 / 上下文补全）"""
    req = RAGRequest(question=question, top_k=top_k, llm_backend=llm_backend,
                     use_hybrid=use_hybrid, use_multi_query=use_multi_query,
                     use_rerank=use_rerank, user_id=user_id,
                     use_rewrite=use_rewrite, use_hyde=use_hyde,
                     use_decompose=use_decompose, use_compress=use_compress,
                     use_few_shot=use_few_shot, use_cot=use_cot)
    return await ask(req)


# ═══════════════════════════════════════════════════════════════
# 文档导入
# ═══════════════════════════════════════════════════════════════

@router.post("/ingest/document", response_model=IngestResponse, tags=["摄取"])
async def ingest_document(file: UploadFile = File(...), owner_id: int = 1):
    """导入多格式文档。委托给统一摄取管道。"""
    try:
        app = _get_app()
        from ..ingest.parsers import SUPPORTED_EXTENSIONS

        suffix = Path(file.filename).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            if suffix == ".doc":
                raise HTTPException(status_code=400, detail="不支持旧版 .doc，请转换为 .docx")
            raise HTTPException(status_code=400, detail=f"不支持的格式: {suffix}")

        safe_name = _safe_filename(file.filename)
        temp_path = Path(app.settings.raw_dir) / "temp" / safe_name
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(await file.read())

        from ..ingest.pipeline import ingest_document as do_ingest
        result = do_ingest(
            str(temp_path), app.settings, app.vector_store, app.meta_store,
            app.embedder, app.storage, owner_id=owner_id,
        )

        return IngestResponse(
            doc_id=result["doc_id"], version_id=result["version_id"],
            title=result["title"], doc_type=result["format"], format=suffix,
            chunk_count=result["chunks"], char_count=result["chars"],
            small_chunks=result["small_chunks"], big_chunks=result["big_chunks"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("导入文档失败: %s", e)
        raise HTTPException(status_code=500, detail=f"导入文档失败: {e}")


@router.post("/ingest/pdf", response_model=IngestResponse, tags=["摄取"])
async def ingest_pdf(file: UploadFile = File(...), owner_id: int = 1):
    """导入 PDF 文件（委托给通用导入接口）"""
    return await ingest_document(file=file, owner_id=owner_id)


# ═══════════════════════════════════════════════════════════════
# 文档管理
# ═══════════════════════════════════════════════════════════════

@router.get("/documents", response_model=list[DocumentInfo], tags=["管理"])
async def list_documents():
    """列出知识库中的所有文档"""
    try:
        app = _get_app()
        if not app.meta_store:
            return []
        try:
            docs = app.meta_store.list_documents()
        except Exception:
            return []  # PostgreSQL 不可用时返回空列表
        return [
            DocumentInfo(
                id=doc.get("id", 0), title=doc.get("title", ""),
                format=doc.get("format", ""), doc_type=doc.get("format", ""),
                owner_id=doc.get("owner_id", 0), status=doc.get("status", "active"),
                latest_version_id=doc.get("latest_version_id", 0),
                char_count=doc.get("char_count", 0), page_count=doc.get("page_count"),
                created_at=str(doc.get("created_at", "")),
                updated_at=str(doc.get("updated_at", "")),
            )
            for doc in docs
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}", response_model=DocumentInfo, tags=["管理"])
async def get_document(doc_id: int):
    """获取文档详情"""
    try:
        app = _get_app()
        doc = app.meta_store.get_document(doc_id)
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return DocumentInfo(
            id=doc["id"], title=doc["title"], format=doc.get("format", ""),
            doc_type=doc.get("format", ""), owner_id=doc.get("owner_id", 0),
            status=doc.get("status", "active"),
            latest_version_id=doc.get("latest_version_id", 0),
            char_count=doc.get("char_count", 0), page_count=doc.get("page_count"),
            created_at=str(doc.get("created_at", "")),
            updated_at=str(doc.get("updated_at", "")),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{doc_id}/versions", response_model=list[DocumentVersion], tags=["管理"])
async def list_versions(doc_id: int):
    """列出文档的所有版本"""
    try:
        app = _get_app()
        versions = app.meta_store.list_versions(doc_id)
        return [
            DocumentVersion(id=v["id"], doc_id=v["doc_id"],
                            version_number=v["version_number"],
                            chunk_count=v.get("chunk_count", 0),
                            char_count=v.get("char_count", 0),
                            created_at=str(v.get("created_at", "")))
            for v in versions
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{doc_id}", tags=["管理"])
async def delete_document(doc_id: int):
    """软删除文档"""
    try:
        app = _get_app()
        app.meta_store.delete_document(doc_id)
        try:
            app.vector_store.delete_by_filter({"doc_id": doc_id})
        except Exception:
            pass
        return {"message": f"文档 {doc_id} 已标记删除", "doc_id": doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 模板管理
# ═══════════════════════════════════════════════════════════════

@router.post("/templates/upload", response_model=TemplateUploadResponse, tags=["模板"])
async def upload_template(file: UploadFile = File(...), owner_id: int = 1):
    """上传 Word/PPT 模板并解析占位符"""
    try:
        app = _get_app()
        suffix = Path(file.filename).suffix.lower()
        if suffix not in ('.docx', '.pptx'):
            raise HTTPException(status_code=400, detail="仅支持 .docx 和 .pptx 模板")

        safe_name = _safe_filename(file.filename)
        temp_path = Path(app.settings.raw_dir) / "temp" / safe_name
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_bytes(await file.read())

        obj_name = f"tpl_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{safe_name}"
        app.storage.upload_template(temp_path, obj_name)

        from ..generation.template import parse_template
        schema = parse_template(str(temp_path))

        tpl_id = app.meta_store.add_template(
            name=schema.name or Path(file.filename).stem, type=schema.type,
            storage_path=obj_name,
            placeholders_schema={
                "placeholders": [{"id": p.id, "type": p.type, "location": p.location, "hint": p.hint}
                                 for p in schema.placeholders],
                "styles": schema.styles, "layouts": schema.layouts,
            },
            owner_id=owner_id,
        )

        return TemplateUploadResponse(
            id=tpl_id, name=schema.name, type=schema.type,
            placeholders_count=len(schema.placeholders),
            download_url=app.storage.presigned_get_url(obj_name, bucket=app.settings.minio.template_bucket),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates/{tpl_id}/parse", tags=["模板"])
async def parse_template_info(tpl_id: int):
    """获取模板解析信息"""
    try:
        app = _get_app()
        tpl = app.meta_store.get_template(tpl_id)
        if not tpl:
            raise HTTPException(status_code=404, detail="模板不存在")
        return {"id": tpl["id"], "name": tpl["name"], "type": tpl["type"],
                "placeholders_schema": tpl.get("placeholders_schema", {}),
                "storage_path": tpl.get("storage_path", "")}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/templates", tags=["模板"])
async def list_templates(type: str = None):
    """列出所有模板"""
    try:
        app = _get_app()
        if not app.meta_store:
            return []
        try:
            return app.meta_store.list_templates(type=type)
        except Exception:
            return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 文档生成
# ═══════════════════════════════════════════════════════════════

@router.post("/generate", response_model=GenerationResponse, tags=["生成"])
async def generate_document(request: GenerationRequest):
    """基于模板和知识库生成文档"""
    try:
        app = _get_app()
        if not app.llm.is_available():
            raise HTTPException(status_code=503, detail="LLM 不可用")

        tpl = app.meta_store.get_template(request.template_id)
        if not tpl:
            raise HTTPException(status_code=404, detail="模板不存在")

        temp_dir = Path(app.settings.raw_dir) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        tpl_path = temp_dir / f"template_{request.template_id}{'.docx' if tpl['type'] == 'docx' else '.pptx'}"
        app.storage.download_file(tpl["storage_path"], tpl_path,
                                  bucket=app.settings.minio.template_bucket)

        from ..generation.template import parse_template, DocumentGenerator
        schema = parse_template(str(tpl_path))

        rag_context = ""
        if request.use_knowledge_base:
            from ..query.retrieval import build_rag_context
            result = app.pipeline.retrieve(
                query=request.instruction, embedder=app.embedder,
                vector_store=app.vector_store, meta_store=app.meta_store,
                user_id=request.user_id,
            )
            rag_context, _ = build_rag_context(result.hits)

        gen = DocumentGenerator(app.settings, app.llm, app.storage)
        content = gen.generate_content(schema, request.instruction, rag_context)

        obj_name = f"gen_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{Path(tpl['storage_path']).name}"
        download_url = gen.fill_and_upload(tpl_path, content, obj_name)

        app.meta_store.audit(request.user_id or 1, "generate", "document", "",
                             detail={"template_id": request.template_id, "instruction": request.instruction})

        return GenerationResponse(
            download_url=download_url, template_name=tpl["name"],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 权限管理
# ═══════════════════════════════════════════════════════════════

@router.post("/permissions", tags=["权限"])
async def set_permission(request: PermissionRequest):
    """设置文档权限"""
    try:
        _get_app().meta_store.set_permission(
            request.doc_id, request.principal_type, request.principal_id, request.mask)
        return {"message": "权限已设置", "doc_id": request.doc_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/permissions/{doc_id}", tags=["权限"])
async def get_permissions(doc_id: int):
    """查看文档权限"""
    try:
        return _get_app().meta_store.get_permissions(doc_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 摘要
# ═══════════════════════════════════════════════════════════════

@router.post("/summarize", response_model=SummarizeResponse, tags=["查询"])
async def summarize(request: SummarizeRequest):
    """为已导入的文档生成摘要"""
    try:
        app = _get_app()
        if request.llm_backend:
            app = bootstrap(llm_backend=request.llm_backend)

        if not app.llm.is_available():
            raise HTTPException(status_code=503, detail="LLM 不可用")

        from ..query.summarize import summarize_document
        summary = summarize_document(request.source, app.settings, app.vector_store,
                                     app.meta_store, app.embedder, app.llm)
        return SummarizeResponse(source=request.source, summary=summary)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 多轮对话
# ═══════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    session_id: Optional[str] = None
    top_k: int = Field(5, ge=1, le=20)
    llm_backend: Optional[str] = None
    user_id: Optional[int] = None
    use_few_shot: bool = Field(True, description="启用 Few-Shot 示例引导")
    use_cot: bool = Field(True, description="启用 Chain-of-Thought 分步推理")


class ChatResponse(BaseModel):
    answer: str
    sources: list[RAGSource] = []
    session_id: str
    message_count: int = 0


_conversation_memory = None


def _get_memory():
    global _conversation_memory
    if _conversation_memory is None:
        from ..query.memory import ConversationMemory
        _conversation_memory = ConversationMemory()
    return _conversation_memory


@router.post("/chat", response_model=ChatResponse, tags=["对话"])
async def chat(request: ChatRequest):
    """多轮对话 RAG"""
    try:
        app = _get_app()
        if request.llm_backend:
            app = bootstrap(llm_backend=request.llm_backend)

        if not app.llm.is_available():
            raise HTTPException(status_code=503, detail="LLM 不可用")

        memory = _get_memory()
        session = memory.get_session(request.session_id)
        if session is None:
            session = memory.create_session(request.session_id)

        from ..query.memory import multi_turn_rag
        result = multi_turn_rag(
            request.message, session, app.settings, app.vector_store,
            app.embedder, app.llm, top_k=request.top_k,
            use_few_shot=request.use_few_shot, use_cot=request.use_cot,
        )

        sources = [
            RAGSource(index=s["index"], title=s["title"], source=s["source"],
                      doc_type=s["doc_type"], score=1 - s["score"])
            for s in result["sources"]
        ]
        return ChatResponse(answer=result["answer"], sources=sources,
                            session_id=result["session_id"],
                            message_count=result["message_count"])
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════
# 系统信息 / 健康检查
# ═══════════════════════════════════════════════════════════════

@router.get("/info", response_model=SystemInfo, tags=["系统"])
async def get_info():
    """获取系统状态和配置信息"""
    try:
        app = _get_app()
        docs = []
        if app.meta_store:
            try:
                docs = app.meta_store.list_documents()
            except Exception:
                pass
        vector_count = 0
        try:
            vector_count = app.vector_store.count()
        except Exception:
            pass
        return SystemInfo(
            app_name=app.settings.app_name, version=app.settings.version,
            llm_backend=app.settings.llm.default,
            embedding_model=app.settings.embedding.model_name,
            embedding_dimension=app.settings.embedding.dimension,
            vector_db_provider=app.settings.vector_db.provider,
            document_count=len(docs), total_chunks=vector_count,
            storage_provider="minio" if app.storage.enabled else "local",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", tags=["系统"])
async def health():
    return {"status": "healthy", "version": "2.1.0"}


# ═══════════════════════════════════════════════════════════════
# RAG 评估
# ═══════════════════════════════════════════════════════════════

class RAGEvalRequest(BaseModel):
    query: str = Field(..., description="查询")
    top_k: int = Field(5, ge=1, le=20)
    llm_backend: Optional[str] = None
    use_rerank: bool = Field(True)


class RAGEvalResponse(BaseModel):
    query: str
    answer: str
    metrics: dict


@router.post("/evaluate", response_model=RAGEvalResponse, tags=["评估"])
async def evaluate_rag(request: RAGEvalRequest):
    """评估 RAG 问答质量"""
    try:
        app = _get_app()
        if request.llm_backend:
            app = bootstrap(llm_backend=request.llm_backend)

        if not app.llm.is_available():
            raise HTTPException(status_code=503, detail="LLM 不可用")

        from ..query.rag import rag_answer
        from ..query.evaluation import rag_evaluate

        result = rag_answer(
            request.query, app.settings, app.vector_store, app.embedder, app.llm,
            meta_store=app.meta_store, top_k=request.top_k, use_rerank=request.use_rerank,
            pipeline=app.pipeline,
        )

        context = "\n\n".join([s.get("title", "") for s in result["sources"]])
        evaluation = rag_evaluate(request.query, result["answer"], result["sources"],
                                  context, llm=app.llm, k=request.top_k)

        return RAGEvalResponse(query=request.query, answer=result["answer"],
                               metrics=evaluation.metrics)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
