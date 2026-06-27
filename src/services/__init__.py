"""服务层 — 企业级微服务模块

按新方案将系统拆分为独立服务模块:

  - UserService:     用户、角色、权限管理
  - DocumentService: 文档元数据、分类、标签、版本
  - ParseService:    多格式深度解析、排版提取
  - EmbeddingService: 嵌入向量化
  - RetrievalService: 语义搜索、混合检索、重排序、权限过滤
  - LLMService:      LLM 托管、问答生成、文档内容策划
  - GenerationService: Word/PPT 模板填充与文件合成
  - StorageService:  MinIO 对象存储管理
  - AuditService:    审计日志

"""

from .document import DocumentService
from .retrieval import RetrievalService
from .generation import GenerationService

__all__ = [
    "DocumentService",
    "RetrievalService",
    "GenerationService",
]
