"""FastAPI Web API 层 — 为前端提供 RESTful 接口

启动方式:
    python -m src.api
    或: uvicorn src.api:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import os
import re
import sys
import shutil
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# 确保项目根目录在 sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import load_settings, Settings
from src.store.vector import VectorStore
from src.store.metadata import MetadataStore
from src.store.embedding import EmbeddingManager
from src.llm.base import get_llm

# ── App ──────────────────────────────────────────────────

app = FastAPI(
    title="个人知识库 API",
    description="本地 RAG 知识库系统 RESTful 接口",
    version="1.0.0",
)

# CORS — 允许 Vue3 前端跨域
# 安全改进：限制允许的来源，避免使用 "*" + credentials 组合
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局组件（启动时初始化） ─────────────────────────────

settings: Settings = None
embedder: EmbeddingManager = None
vector_store: VectorStore = None
meta_store: MetadataStore = None
llm_instance = None


@app.on_event("startup")
def startup():
    global settings, embedder, vector_store, meta_store, llm_instance
    settings = load_settings()
    embedder = EmbeddingManager(settings)
    vector_store = VectorStore(settings)
    meta_store = MetadataStore(settings)
    llm_instance = get_llm(settings.llm.default, settings)


@app.on_event("shutdown")
def shutdown():
    if meta_store:
        meta_store.close()


# ── 请求/响应模型 ────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词或自然语言描述")
    top_k: int = Field(5, ge=1, le=50, description="返回结果数量")


class SearchResultItem(BaseModel):
    text: str
    source: str
    title: str
    doc_type: str
    score: float
    chunk_idx: int


class AskRequest(BaseModel):
    question: str = Field(..., description="自然语言问题")
    top_k: int = Field(5, ge=1, le=20, description="检索文档数量")
    llm_backend: Optional[str] = Field(None, description="LLM 后端: claude | ollama")


class AskResponse(BaseModel):
    answer: str
    sources: list[dict]


class SummarizeRequest(BaseModel):
    source: str = Field(..., description="文档来源（文件路径或 URL）")
    llm_backend: Optional[str] = Field(None, description="LLM 后端")


class DocumentInfo(BaseModel):
    id: int
    source: str
    doc_type: str
    title: str
    chunk_count: int
    char_count: int
    created_at: str


class StatusResponse(BaseModel):
    llm_backend: str
    claude_model: str
    ollama_model: str
    embedding_model: str
    embedding_device: str
    document_count: int
    vector_count: int
    chroma_path: str


class IngestResponse(BaseModel):
    title: str
    chunks: int
    chars: int
    message: str


# ── 文档管理 ─────────────────────────────────────────────

@app.get("/api/documents", response_model=list[DocumentInfo], tags=["文档管理"])
def list_documents():
    """列出知识库中的所有文档。"""
    docs = meta_store.list_documents()
    return docs


@app.post("/api/documents/upload", response_model=IngestResponse, tags=["文档管理"])
async def upload_pdf(file: UploadFile = File(...)):
    """上传并导入 PDF 文件。"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "仅支持 PDF 文件")

    # 保存到临时文件
    # 安全改进：清洗文件名，防止路径遍历
    safe_name = Path(file.filename).name
    safe_name = re.sub(r'[^\w\s\-\.]', '', safe_name)
    if not safe_name:
        safe_name = "uploaded_file.pdf"

    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / safe_name

    try:
        with open(tmp_path, "wb") as f:
            content = await file.read()
            f.write(content)

        from src.ingest.pipeline import ingest_document as ingest_pdf
        result = ingest_pdf(str(tmp_path), settings, vector_store, meta_store, embedder)

        return IngestResponse(
            title=result["title"],
            chunks=result["chunks"],
            chars=result["chars"],
            message=f"成功导入: {result['title']} ({result['chunks']} 块)",
        )
    except Exception as e:
        raise HTTPException(500, f"导入失败: {str(e)}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


class UrlRequest(BaseModel):
    url: str = Field(..., description="网页 URL")


@app.post("/api/documents/url", response_model=IngestResponse, tags=["文档管理"])
def import_url(req: UrlRequest):
    """导入网页内容。"""
    try:
        from src.ingest.pipeline import ingest_webpage
        result = ingest_webpage(req.url, settings, vector_store, meta_store, embedder)
        return IngestResponse(
            title=result["title"],
            chunks=result["chunks"],
            chars=result["chars"],
            message=f"成功导入: {result['title']} ({result['chunks']} 块)",
        )
    except Exception as e:
        raise HTTPException(500, f"导入失败: {str(e)}")


@app.delete("/api/documents", tags=["文档管理"])
def delete_document(source: str = Query(..., description="文档来源路径或 URL")):
    """删除指定文档及其所有向量块。"""
    count = vector_store.delete_by_source(source)
    meta_store.delete_document(source)
    return {"deleted_chunks": count, "source": source}


# ── 搜索与问答 ───────────────────────────────────────────

@app.post("/api/search", response_model=list[SearchResultItem], tags=["搜索与问答"])
def search(req: SearchRequest):
    """语义搜索知识库。"""
    from src.query.search import semantic_search
    results = semantic_search(req.query, vector_store, embedder, top_k=req.top_k)
    return [
        SearchResultItem(
            text=r.text,
            source=r.source,
            title=r.title,
            doc_type=r.doc_type,
            score=r.score,
            chunk_idx=r.chunk_idx,
        )
        for r in results
    ]


@app.post("/api/ask", response_model=AskResponse, tags=["搜索与问答"])
def ask(req: AskRequest):
    """RAG 问答 — 基于知识库回答问题。"""
    llm = llm_instance
    if req.llm_backend:
        llm = get_llm(req.llm_backend, settings)

    if not llm.is_available():
        raise HTTPException(503, f"LLM 后端 ({req.llm_backend or settings.llm.default}) 不可用")

    from src.query.rag import rag_answer
    result = rag_answer(req.question, settings, vector_store, embedder, llm, top_k=req.top_k)
    return AskResponse(answer=result["answer"], sources=result["sources"])


@app.post("/api/summarize", tags=["搜索与问答"])
def summarize(req: SummarizeRequest):
    """为已导入的文档生成摘要。"""
    llm = llm_instance
    if req.llm_backend:
        llm = get_llm(req.llm_backend, settings)

    if not llm.is_available():
        raise HTTPException(503, f"LLM 后端不可用")

    from src.query.summarize import summarize_document
    summary = summarize_document(
        req.source, settings, vector_store, meta_store, embedder, llm
    )
    return {"source": req.source, "summary": summary}


# ── 系统状态 ─────────────────────────────────────────────

@app.get("/api/status", response_model=StatusResponse, tags=["系统"])
def get_status():
    """获取系统状态信息。"""
    docs = meta_store.list_documents()
    return StatusResponse(
        llm_backend=settings.llm.default,
        claude_model=settings.llm.claude_model,
        ollama_model=settings.llm.ollama_model,
        embedding_model=settings.embedding.model_name,
        embedding_device=settings.embedding.device,
        document_count=len(docs),
        vector_count=vector_store.count(),
        chroma_path=str(settings.chroma_dir),
    )



# ── RAG 评估 ─────────────────────────────────────────────

class EvalRequest(BaseModel):
    test_cases: list[dict] = Field(..., description="测试用例列表 [{question, expected_sources}]")
    top_k: int = Field(5, ge=1, le=50, description="检索 Top-K")


class EvalFromFileRequest(BaseModel):
    test_file: str = Field(..., description="测试用例 JSON 文件路径")
    top_k: int = Field(5, ge=1, le=50, description="检索 Top-K")


@app.post("/api/eval", tags=["评估"])
def run_eval(req: EvalRequest):
    """运行 RAG 检索质量评估。"""
    from src.eval.recall import TestCase, evaluate_batch

    cases = [
        TestCase(question=tc["question"], expected_sources=tc.get("expected_sources", []))
        for tc in req.test_cases
    ]
    result = evaluate_batch(cases, vector_store, embedder, top_k=req.top_k)
    return result


@app.post("/api/eval/file", tags=["评估"])
def run_eval_from_file(req: EvalFromFileRequest):
    """从文件加载测试用例并运行评估。"""
    from src.eval.recall import load_test_cases, evaluate_batch

    if not os.path.exists(req.test_file):
        raise HTTPException(404, f"测试文件不存在: {req.test_file}")

    cases = load_test_cases(req.test_file)
    result = evaluate_batch(cases, vector_store, embedder, top_k=req.top_k)
    return result


@app.get("/api/health", tags=["系统"])
def health_check():
    """健康检查。"""
    return {"status": "ok"}


# ── 前端页面 ────────────────────────────────────────────

WEB_DIR = ROOT / "web"

@app.get("/", include_in_schema=False)
def serve_index():
    """返回前端首页。"""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "API 服务运行中，请访问 /docs 查看接口文档"}


# 静态文件（CSS/JS/图片等）
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


# ── 直接运行 ─────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api:app", host="0.0.0.0", port=8000, reload=True)
