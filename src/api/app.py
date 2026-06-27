"""FastAPI Web API 入口 — 企业版 v2.0

微服务架构 API 网关:
  - 用户服务（认证鉴权）
  - 文档服务（元数据、版本、权限）
  - 解析服务（多格式深度解析）
  - 嵌入服务（向量化）
  - 检索服务（语义搜索、混合检索、重排序）
  - LLM/生成服务（问答、文档生成）
  - 存储服务（MinIO 对象管理）
  - 审计服务（操作日志）
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .routes import router

app = FastAPI(
    title="🧠 RAG Knowledge Base — Enterprise",
    description="""企业级多格式 RAG 智能知识库与文档生成系统

## 核心能力

- **多格式摄入**: Word、PPT、Excel、PDF、图片等深度解析 + 排版保留
- **语义检索**: 向量检索 + 混合检索 + Cross-Encoder 重排序
- **智能问答**: 基于知识库片段的精准答案，标注引用来源
- **版本管理**: 文档更新后自动淘汰旧版本块
- **权限控制**: RBAC 模型，向量数据库标量过滤
- **文档生成**: 模板化 Word/PPT 自动生成
- **审计日志**: 全操作链路追踪
""",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
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
        "name": "🧠 RAG Knowledge Base — Enterprise",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "running",
        "services": {
            "user_service": "/api/users",
            "document_service": "/api/documents",
            "search_service": "/api/search",
            "generation_service": "/api/generate",
            "health": "/api/health",
        },
    }


# 静态文件
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")
