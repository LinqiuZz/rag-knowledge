"""全局配置加载器"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field

import yaml

# 项目根目录 (E:\Rag)
ROOT = Path(__file__).resolve().parent.parent


def _get_secret(key: str, default: str = "") -> str:
    """
    获取密钥值（支持云端密钥服务）

    优先级：环境变量 > 云端密钥服务 > .env 文件 > 默认值
    """
    try:
        from .secrets import get_secret
        return get_secret(key, default)
    except ImportError:
        # 如果 secrets 模块不可用，回退到环境变量
        return os.environ.get(key, default)

@dataclass
class LLMConfig:
    default: str = "claude"
    claude_model: str = "mimo-v2.5-pro"
    claude_base_url: str = "https://token-plan-cn.xiaomimimo.com/anthropic"
    claude_api_key: str = ""
    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"

@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-small-zh-v1.5"
    device: str = "cuda"
    dimension: int = 512

@dataclass
class ChunkingConfig:
    size: int = 512
    overlap: int = 64
    strategy: str = "sentence"  # recursive | sentence | paragraph

@dataclass
class MySQLConfig:
    host: str = "localhost"
    port: int = 3306
    user: str = "Lin"
    password: str = ""
    database: str = "rag_meta"

@dataclass
class StoreConfig:
    chroma_path: str = "data/db/chroma"

@dataclass
class IngestConfig:
    raw_dir: str = "data/raw"
    max_file_size_mb: int = 50

@dataclass
class Settings:
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    store: StoreConfig = field(default_factory=StoreConfig)
    mysql: MySQLConfig = field(default_factory=MySQLConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)

    def validate(self) -> list[str]:
        """验证配置，返回问题列表。"""
        issues = []

        # LLM 配置验证
        if self.llm.default not in ("claude", "ollama"):
            issues.append(f"llm.default={self.llm.default} 无效，应为 claude 或 ollama")

        # Embedding 配置验证
        if self.embedding.device not in ("cpu", "cuda"):
            issues.append(f"embedding.device={self.embedding.device} 无效，应为 cpu 或 cuda")
        if self.embedding.dimension not in (384, 512, 768, 1024):
            issues.append(f"embedding.dimension={self.embedding.dimension} 非常见值")

        # Chunking 配置验证
        if self.chunking.size < 64:
            issues.append("chunking.size 过小，建议 >= 256")
        if self.chunking.size > 10000:
            issues.append("chunking.size 过大，建议 <= 2000")
        if self.chunking.overlap < 0:
            issues.append("chunking.overlap 不能为负数")
        if self.chunking.overlap >= self.chunking.size:
            issues.append("chunking.overlap 应小于 chunking.size")
        if self.chunking.strategy not in ("recursive", "sentence", "paragraph"):
            issues.append(f"chunking.strategy={self.chunking.strategy} 无效")

        # Ingest 配置验证
        if self.ingest.max_file_size_mb < 1:
            issues.append("ingest.max_file_size_mb 过小")
        if self.ingest.max_file_size_mb > 1000:
            issues.append("ingest.max_file_size_mb 过大，建议 <= 500")

        # MySQL 配置验证
        if self.mysql.port < 1 or self.mysql.port > 65535:
            issues.append(f"mysql.port={self.mysql.port} 无效")

        return issues

    @property
    def chroma_dir(self) -> Path:
        return ROOT / self.store.chroma_path

    @property
    def raw_dir(self) -> Path:
        return ROOT / self.ingest.raw_dir

def load_settings(config_path: str | Path | None = None) -> Settings:
    """从 config.yaml 加载配置，缺失字段用默认值填充。"""
    # 加载 .env 文件（在读取配置之前）
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass
    path = Path(config_path) if config_path else ROOT / "config.yaml"
    s = Settings()

    if not path.exists():
        return s

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    # LLM
    llm = raw.get("llm", {})
    s.llm.default = llm.get("default", s.llm.default)
    claude = llm.get("claude", {})
    s.llm.claude_model = claude.get("model", s.llm.claude_model)
    s.llm.claude_base_url = claude.get("base_url", s.llm.claude_base_url)
    # API Key: 优先云端密钥服务，其次环境变量，最后配置文件
    s.llm.claude_api_key = (
        _get_secret("ANTHROPIC_API_KEY")
        or _get_secret("ANTHROPIC_AUTH_TOKEN")
        or claude.get("api_key", "")
    )
    ollama = llm.get("ollama", {})
    s.llm.ollama_model = ollama.get("model", s.llm.ollama_model)
    s.llm.ollama_url = ollama.get("url", s.llm.ollama_url)

    # Embedding
    emb = raw.get("embedding", {})
    s.embedding.model_name = emb.get("model_name", s.embedding.model_name)
    s.embedding.device = emb.get("device", s.embedding.device)
    s.embedding.dimension = emb.get("dimension", s.embedding.dimension)

    # Chunking
    ch = raw.get("chunking", {})
    s.chunking.size = ch.get("size", s.chunking.size)
    s.chunking.overlap = ch.get("overlap", s.chunking.overlap)
    s.chunking.strategy = ch.get("strategy", s.chunking.strategy)

    # Store
    st = raw.get("store", {})
    s.store.chroma_path = st.get("chroma_path", s.store.chroma_path)

    # MySQL — 敏感信息优先从云端密钥服务获取
    mysql = raw.get("mysql", {})
    s.mysql.host = _get_secret("MYSQL_HOST", mysql.get("host", s.mysql.host))
    s.mysql.port = int(_get_secret("MYSQL_PORT", str(mysql.get("port", s.mysql.port))))
    s.mysql.user = _get_secret("MYSQL_USER", mysql.get("user", s.mysql.user))
    s.mysql.password = _get_secret("MYSQL_PASSWORD", mysql.get("password", ""))
    s.mysql.database = _get_secret("MYSQL_DATABASE", mysql.get("database", s.mysql.database))

    # Ingest
    ing = raw.get("ingest", {})
    s.ingest.raw_dir = ing.get("raw_dir", s.ingest.raw_dir)
    s.ingest.max_file_size_mb = ing.get("max_file_size_mb", s.ingest.max_file_size_mb)

    return s
