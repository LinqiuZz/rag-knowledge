"""文档服务 — 文档元数据、分类、标签、版本管理"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class DocumentService:
    """文档管理服务。

    职责:
      - 文档元数据 CRUD
      - 版本生命周期管理（is_active 标记）
      - 权限绑定
      - 分类与标签
    """

    def __init__(self, meta_store, storage=None):
        self.meta = meta_store
        self.storage = storage

    def create_document(
        self, title: str, format: str, owner_id: int = 1,
        storage_path: str = "", char_count: int = 0,
        page_count: int = None,
    ) -> int:
        """创建文档记录。"""
        return self.meta.add_document(
            title=title,
            format=format,
            owner_id=owner_id,
            storage_path=storage_path,
            char_count=char_count,
            page_count=page_count,
        )

    def create_version(self, doc_id: int, storage_path: str,
                       char_count: int = 0, page_count: int = None) -> int:
        """创建新版本，自动停用旧版本块。"""
        return self.meta.create_version(
            doc_id=doc_id,
            storage_path=storage_path,
            char_count=char_count,
            page_count=page_count,
        )

    def get_document(self, doc_id: int) -> dict | None:
        return self.meta.get_document(doc_id)

    def list_documents(self, status: str = "active") -> list[dict]:
        return self.meta.list_documents(status)

    def list_versions(self, doc_id: int) -> list[dict]:
        return self.meta.list_versions(doc_id)

    def delete_document(self, doc_id: int):
        self.meta.delete_document(doc_id)

    def set_permission(self, doc_id: int, principal_type: str,
                       principal_id: int, mask: int = 1):
        """设置文档级权限。"""
        self.meta.set_permission(doc_id, principal_type, principal_id, mask)

    def get_permissions(self, doc_id: int) -> list[dict]:
        return self.meta.get_permissions(doc_id)

    def get_accessible_docs(self, user_id: int) -> list[int]:
        """获取用户可访问的文档 ID 列表。"""
        return self.meta.get_accessible_doc_ids(user_id)

    def audit(self, user_id: int, action: str, target_type: str = "",
              target_id: str = "", detail: dict = None):
        self.meta.audit(user_id, action, target_type, target_id, detail=detail)
