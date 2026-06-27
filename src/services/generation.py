"""文档生成服务 — 模板解析、内容填充、文件合成"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GenerationService:
    """文档生成服务。

    职责:
      - 模板解析（占位符提取）
      - LLM 内容策划
      - Word/PPT 文件填充合成
      - 与知识库集成（RAG 增强生成）
    """

    def __init__(self, settings, llm=None, storage=None,
                 retrieval_service=None):
        self.settings = settings
        self.llm = llm
        self.storage = storage
        self.retrieval = retrieval_service

    def parse_template(self, file_path: str | Path):
        """解析模板，提取占位符清单。"""
        from ..generation.template import parse_template
        return parse_template(file_path)

    def generate_content(self, schema, instruction: str,
                         use_knowledge_base: bool = True,
                         user_id: int = None) -> dict:
        """基于模板 Schema 和指令生成填充内容。

        Args:
            schema: TemplateSchema 对象
            instruction: 用户填充需求
            use_knowledge_base: 是否从知识库检索
            user_id: 用户 ID

        Returns:
            填充内容 dict
        """
        from ..generation.template import DocumentGenerator

        rag_context = ""
        if use_knowledge_base and self.retrieval:
            result = self.retrieval.search(
                query=instruction,
                top_k=5,
                user_id=user_id,
            )
            rag_context = result.get("context", "")

        gen = DocumentGenerator(self.settings, self.llm, self.storage)
        return gen.generate_content(schema, instruction, rag_context)

    def fill_template(self, template_path: str | Path, content: dict,
                      output_path: str | Path = None) -> Path:
        """用内容填充模板。"""
        from ..generation.template import DocumentGenerator

        gen = DocumentGenerator(self.settings, self.llm, self.storage)
        return gen.fill_template(template_path, content, output_path)

    def fill_and_upload(self, template_path: str | Path, content: dict,
                        object_name: str = None) -> str:
        """填充模板并上传，返回下载链接。"""
        from ..generation.template import DocumentGenerator

        gen = DocumentGenerator(self.settings, self.llm, self.storage)
        return gen.fill_and_upload(template_path, content, object_name)
