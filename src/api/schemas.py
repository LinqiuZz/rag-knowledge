"""API 数据模型"""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional


class SearchRequest(BaseModel):
    """搜索请求"""
    query: str = Field(..., description="搜索关键词或自然语言描述")
    top_k: int = Field(5, ge=1, le=20, description="返回结果数量")


class SearchResultItem(BaseModel):
    """搜索结果项"""
    text: str = Field(..., description="文档块文本")
    source: str = Field(..., description="来源路径")
    title: str = Field(..., description="文档标题")
    doc_type: str = Field(..., description="文档类型")
    score: float = Field(..., description="相似度分数 (0-1)")
    chunk_idx: int = Field(..., description="块索引")


class SearchResponse(BaseModel):
    """搜索响应"""
    results: list[SearchResultItem] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="结果总数")


class RAGRequest(BaseModel):
    """RAG 问答请求"""
    question: str = Field(..., description="问题")
    top_k: int = Field(5, ge=1, le=20, description="检索文档数量")
    llm_backend: Optional[str] = Field(None, description="LLM 后端 (claude|ollama)")


class RAGSource(BaseModel):
    """RAG 引用来源"""
    index: int = Field(..., description="来源序号")
    title: str = Field(..., description="文档标题")
    source: str = Field(..., description="来源路径")
    doc_type: str = Field(..., description="文档类型")
    score: float = Field(..., description="相关度分数")


class RAGResponse(BaseModel):
    """RAG 问答响应"""
    answer: str = Field(..., description="生成的回答")
    sources: list[RAGSource] = Field(..., description="引用来源列表")


class IngestResponse(BaseModel):
    """文档导入响应"""
    title: str = Field(..., description="文档标题")
    chunk_count: int = Field(..., description="分块数量")
    char_count: int = Field(..., description="字符总数")
    doc_type: str = Field(..., description="文档类型")


class SummarizeRequest(BaseModel):
    """摘要请求"""
    source: str = Field(..., description="文档来源（文件路径或 URL）")
    llm_backend: Optional[str] = Field(None, description="LLM 后端")


class SummarizeResponse(BaseModel):
    """摘要响应"""
    source: str = Field(..., description="文档来源")
    summary: str = Field(..., description="生成的摘要")


class DocumentInfo(BaseModel):
    """文档信息"""
    title: str = Field(..., description="文档标题")
    doc_type: str = Field(..., description="文档类型")
    chunk_count: int = Field(..., description="块数量")
    char_count: int = Field(..., description="字符数")
    created_at: str = Field(..., description="导入时间")


class SystemInfo(BaseModel):
    """系统信息"""
    llm_backend: str = Field(..., description="当前 LLM 后端")
    embedding_model: str = Field(..., description="嵌入模型")
    document_count: int = Field(..., description="文档数量")
    total_chunks: int = Field(..., description="总块数")


class ErrorResponse(BaseModel):
    """错误响应"""
    detail: str = Field(..., description="错误详情")
