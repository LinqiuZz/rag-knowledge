"""API 数据模型 — 企业版"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


# ═══════════════════════════════════════════════════════════════
# 搜索
# ═══════════════════════════════════════════════════════════════

class SearchRequest(BaseModel):
    query: str = Field(..., description="搜索关键词或自然语言描述")
    top_k: int = Field(5, ge=1, le=50, description="返回结果数量")
    use_hybrid: bool = Field(False, description="是否使用混合检索")
    user_id: Optional[int] = Field(None, description="用户ID（权限过滤）")


class SearchResultItem(BaseModel):
    text: str = Field(..., description="文档块文本")
    source: str = Field("", description="来源路径")
    title: str = Field("", description="文档标题")
    doc_type: str = Field("", description="文档类型")
    doc_id: int = Field(0, description="文档ID")
    score: float = Field(..., description="相似度/综合分数 (0-1)")
    chunk_idx: int = Field(0, description="块索引")
    page_number: int = Field(0, description="页码")
    slide_number: int = Field(0, description="幻灯片号")
    element_type: str = Field("Paragraph", description="元素类型")


class SearchResponse(BaseModel):
    results: list[SearchResultItem] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="结果总数")
    retrieval_stats: Optional[dict] = Field(None, description="检索统计")


# ═══════════════════════════════════════════════════════════════
# RAG 问答
# ═══════════════════════════════════════════════════════════════

class RAGRequest(BaseModel):
    question: str = Field(..., description="问题")
    top_k: int = Field(5, ge=1, le=20, description="检索文档数量")
    llm_backend: Optional[str] = Field(None, description="LLM 后端 (claude|ollama)")
    use_hybrid: bool = Field(False, description="是否使用混合检索")
    use_multi_query: bool = Field(False, description="是否使用多查询扩展")
    use_rerank: bool = Field(True, description="是否使用重排序")
    user_id: Optional[int] = Field(None, description="用户ID（权限过滤）")
    # ── 查询改写 ──
    use_rewrite: bool = Field(True, description="启用查询改写（总开关）")
    use_hyde: bool = Field(True, description="启用 HyDE 语义增强")
    use_decompose: bool = Field(True, description="启用任务分解")
    use_compress: bool = Field(True, description="启用上下文补全")
    history: Optional[list[dict]] = Field(None, description="多轮对话历史")
    # ── Prompt 增强 ──
    use_few_shot: bool = Field(True, description="启用 Few-Shot 示例引导")
    use_cot: bool = Field(True, description="启用 Chain-of-Thought 分步推理")


class RAGSource(BaseModel):
    index: int = Field(..., description="来源序号")
    title: str = Field("", description="文档标题")
    source: str = Field("", description="来源路径")
    doc_type: str = Field("", description="文档类型")
    score: float = Field(..., description="相关度分数")
    page_number: int = Field(0, description="页码")
    slide_number: int = Field(0, description="幻灯片号")
    element_type: str = Field("Paragraph", description="元素类型")
    chunk_id: str = Field("", description="块ID")


class RAGResponse(BaseModel):
    answer: str = Field(..., description="生成的回答")
    sources: list[RAGSource] = Field(..., description="引用来源列表")


# ═══════════════════════════════════════════════════════════════
# 文档管理
# ═══════════════════════════════════════════════════════════════

class DocumentInfo(BaseModel):
    id: int = Field(..., description="文档ID")
    title: str = Field(..., description="文档标题")
    format: str = Field(..., description="文档格式")
    doc_type: str = Field("", description="文档类型（兼容）")
    owner_id: int = Field(0, description="所有者ID")
    status: str = Field("active", description="状态")
    latest_version_id: int = Field(0, description="最新版本ID")
    char_count: int = Field(0, description="字符数")
    page_count: Optional[int] = Field(None, description="页数")
    chunk_count: int = Field(0, description="块数")
    created_at: str = Field("", description="创建时间")
    updated_at: str = Field("", description="更新时间")


class DocumentVersion(BaseModel):
    id: int = Field(..., description="版本ID")
    doc_id: int = Field(..., description="文档ID")
    version_number: int = Field(..., description="版本号")
    chunk_count: int = Field(0, description="块数")
    char_count: int = Field(0, description="字符数")
    created_at: str = Field("", description="创建时间")


class IngestResponse(BaseModel):
    doc_id: int = Field(..., description="文档ID")
    version_id: int = Field(0, description="版本ID")
    title: str = Field(..., description="文档标题")
    doc_type: str = Field(..., description="文档类型")
    format: str = Field("", description="文件格式")
    chunk_count: int = Field(0, description="分块数量")
    char_count: int = Field(0, description="字符总数")
    small_chunks: int = Field(0, description="子块数量")
    big_chunks: int = Field(0, description="父块数量")


# ═══════════════════════════════════════════════════════════════
# 模板与文档生成
# ═══════════════════════════════════════════════════════════════

class TemplateUploadResponse(BaseModel):
    id: int = Field(..., description="模板ID")
    name: str = Field(..., description="模板名称")
    type: str = Field(..., description="模板类型 (docx|pptx)")
    placeholders_count: int = Field(0, description="占位符数量")
    download_url: str = Field("", description="模板下载链接")


class GenerationRequest(BaseModel):
    template_id: int = Field(..., description="模板ID")
    instruction: str = Field(..., description="填充指令（如：根据Q3销售数据填充）")
    use_knowledge_base: bool = Field(True, description="是否从知识库检索数据")
    user_id: Optional[int] = Field(None, description="用户ID")


class GenerationResponse(BaseModel):
    download_url: str = Field(..., description="生成文件下载链接")
    template_name: str = Field("", description="模板名称")
    generated_at: str = Field("", description="生成时间")


# ═══════════════════════════════════════════════════════════════
# 权限管理
# ═══════════════════════════════════════════════════════════════

class PermissionRequest(BaseModel):
    doc_id: int = Field(..., description="文档ID")
    principal_type: str = Field(..., description="主体类型 (user|role|department)")
    principal_id: int = Field(..., description="主体ID")
    mask: int = Field(1, description="权限掩码 (1=读, 2=写, 4=删)")


# ═══════════════════════════════════════════════════════════════
# 系统
# ═══════════════════════════════════════════════════════════════

class SystemInfo(BaseModel):
    app_name: str = Field("RAG-KnowledgeBase", description="应用名称")
    version: str = Field("2.1.0", description="版本")
    llm_backend: str = Field(..., description="当前 LLM 后端")
    embedding_model: str = Field(..., description="嵌入模型")
    embedding_dimension: int = Field(0, description="嵌入维度")
    vector_db_provider: str = Field("", description="向量数据库类型")
    document_count: int = Field(0, description="文档数量")
    total_chunks: int = Field(0, description="总块数")
    storage_provider: str = Field("minio", description="文件存储类型")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="错误详情")


# ═══════════════════════════════════════════════════════════════
# 兼容旧接口
# ═══════════════════════════════════════════════════════════════

class SummarizeRequest(BaseModel):
    source: str = Field(..., description="文档来源")
    llm_backend: Optional[str] = Field(None, description="LLM 后端")


class SummarizeResponse(BaseModel):
    source: str = Field(..., description="文档来源")
    summary: str = Field(..., description="生成的摘要")
