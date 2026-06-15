"""FastAPI Web API 入口"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import router

app = FastAPI(
    title="📚 个人知识库 API",
    description="本地离线个人知识库系统 — 支持 PDF/网页导入、语义搜索、RAG 问答",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置（允许前端跨域访问）
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

# 注册路由
app.include_router(router, prefix="/api")

# 前端目录
WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


@app.get("/", include_in_schema=False)
async def serve_index():
    """返回前端页面"""
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {
        "name": "📚 个人知识库 API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "running",
    }


# 静态文件
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}
