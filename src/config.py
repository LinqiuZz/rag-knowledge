"""全局配置加载器 — 企业级多服务架构"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Literal

import yaml

ROOT = Path(__file__).resolve().parent.parent


def _get_secret(key: str, default: str = "") -> str:
    """获取密钥值（支持云端密钥服务）
    优先级：环境变量 > 云端密钥服务 > .env 文件 > 默认值
    """
    try:
        from .secrets import get_secret
        return get_secret(key, default)
    except ImportError:
        return os.environ.get(key, default)


# ═══════════════════════════════════════════════════════════════
# LLM 配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class LLMConfig:
    default: str = "claude"
    # Claude / Anthropic 兼容
    claude_model: str = "mimo-v2.5-pro"
    claude_base_url: str = "https://token-plan-cn.xiaomimimo.com/anthropic"
    claude_api_key: str = ""
    # Ollama 本地
    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    # 通用参数
    max_tokens: int = 2048
    temperature: float = 0.1


# ═══════════════════════════════════════════════════════════════
# Embedding 配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-m3"             # 新方案推荐 BGE-M3，支持稠密+稀疏混合
    device: str = "cpu"                          # cpu | cuda
    dimension: int = 1024                        # BGE-M3 = 1024 维
    normalize: bool = True
    batch_size: int = 32


# ═══════════════════════════════════════════════════════════════
# 分块配置 (Small-to-Big)
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChunkingConfig:
    # 子块参数（small chunk — 元素级）
    small_size: int = 512
    small_overlap: int = 64
    # 父块参数（big chunk — 章节/幻灯片级）
    big_size: int = 2048
    big_overlap: int = 128
    # 策略
    strategy: str = "small_to_big"  # small_to_big | recursive | sentence | paragraph
    min_chunk_size: int = 100


# ═══════════════════════════════════════════════════════════════
# 向量数据库配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class VectorDBConfig:
    provider: str = "qdrant"       # qdrant | milvus | chroma
    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    # Milvus
    milvus_host: str = "localhost"
    milvus_port: int = 19530
    # Chroma（向后兼容）
    chroma_path: str = "data/db/chroma"
    # 通用
    collection_name: str = "knowledge_base"
    distance_metric: str = "cosine"  # cosine | euclidean | dot


# ═══════════════════════════════════════════════════════════════
# PostgreSQL 配置（元数据主库）
# ═══════════════════════════════════════════════════════════════

@dataclass
class PostgresConfig:
    host: str = "localhost"
    port: int = 5432
    user: str = "rag_admin"
    password: str = ""
    database: str = "rag_platform"


# ═══════════════════════════════════════════════════════════════
# MinIO 配置（对象存储）
# ═══════════════════════════════════════════════════════════════

@dataclass
class MinIOConfig:
    endpoint: str = "localhost:9000"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    secure: bool = False
    raw_bucket: str = "rag-raw-files"
    template_bucket: str = "rag-templates"
    generated_bucket: str = "rag-generated"


# ═══════════════════════════════════════════════════════════════
# 消息队列配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class MQConfig:
    provider: str = "rabbitmq"     # rabbitmq | redis
    # RabbitMQ
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    # 队列名
    parse_queue: str = "doc-parse-queue"
    embed_queue: str = "doc-embed-queue"
    generate_queue: str = "doc-generate-queue"


# ═══════════════════════════════════════════════════════════════
# Redis 配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class RedisConfig:
    url: str = "redis://localhost:6379/0"
    cache_ttl: int = 300  # 默认缓存 5 分钟


# ═══════════════════════════════════════════════════════════════
# 检索配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class RetrievalConfig:
    top_k: int = 50                      # ANN 初筛数量
    final_k: int = 5                     # 最终返回给 LLM 的块数
    rerank_model: str = "BAAI/bge-reranker-large"
    # 加权分数权重
    semantic_weight: float = 0.7
    freshness_weight: float = 0.2
    keyword_weight: float = 0.1


# ═══════════════════════════════════════════════════════════════
# 摄取配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class IngestConfig:
    max_file_size_mb: int = 50
    # OCR
    ocr_enabled: bool = True
    ocr_lang: str = "ch"                 # PaddleOCR 语言
    # 多模态
    multimodal_model: str = "gpt-4o"     # 用于图片描述生成


# ═══════════════════════════════════════════════════════════════
# 主配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class Settings:
    # 基础
    app_name: str = "RAG-KnowledgeBase"
    version: str = "2.0.0"
    debug: bool = False

    # 子配置
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    vector_db: VectorDBConfig = field(default_factory=VectorDBConfig)
    postgres: PostgresConfig = field(default_factory=PostgresConfig)
    minio: MinIOConfig = field(default_factory=MinIOConfig)
    mq: MQConfig = field(default_factory=MQConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    ingest: IngestConfig = field(default_factory=IngestConfig)

    # ── 向后兼容属性 ──────────────────────────────────────────
    @property
    def chroma_dir(self) -> Path:
        return ROOT / self.vector_db.chroma_path

    @property
    def raw_dir(self) -> Path:
        return ROOT / "data" / "raw"

    def validate(self) -> list[str]:
        """验证配置，返回问题列表。"""
        issues = []

        if self.llm.default not in ("claude", "ollama"):
            issues.append(f"llm.default={self.llm.default} 无效，应为 claude 或 ollama")

        if self.embedding.device not in ("cpu", "cuda"):
            issues.append(f"embedding.device={self.embedding.device} 无效，应为 cpu 或 cuda")

        if self.embedding.dimension not in (384, 512, 768, 1024):
            issues.append(f"embedding.dimension={self.embedding.dimension} 非常见值")

        if self.chunking.small_size < 64:
            issues.append("chunking.small_size 过小，建议 >= 256")

        if self.vector_db.provider not in ("qdrant", "milvus", "chroma"):
            issues.append(f"vector_db.provider={self.vector_db.provider} 无效")

        if self.ingest.max_file_size_mb < 1:
            issues.append("ingest.max_file_size_mb 过小")

        return issues


# ═══════════════════════════════════════════════════════════════
# 配置加载
# ═══════════════════════════════════════════════════════════════

def load_settings(config_path: str | Path | None = None) -> Settings:
    """从 config.yaml 加载配置，缺失字段用默认值填充。"""
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

    # ── LLM ──
    llm = raw.get("llm", {})
    s.llm.default = llm.get("default", s.llm.default)
    claude = llm.get("claude", {})
    s.llm.claude_model = claude.get("model", s.llm.claude_model)
    s.llm.claude_base_url = claude.get("base_url", s.llm.claude_base_url)
    s.llm.claude_api_key = (
        _get_secret("ANTHROPIC_API_KEY")
        or _get_secret("ANTHROPIC_AUTH_TOKEN")
        or claude.get("api_key", "")
    )
    ollama = llm.get("ollama", {})
    s.llm.ollama_model = ollama.get("model", s.llm.ollama_model)
    s.llm.ollama_url = ollama.get("url", s.llm.ollama_url)
    s.llm.max_tokens = llm.get("max_tokens", s.llm.max_tokens)
    s.llm.temperature = llm.get("temperature", s.llm.temperature)

    # ── Embedding ──
    emb = raw.get("embedding", {})
    s.embedding.model_name = emb.get("model_name", s.embedding.model_name)
    s.embedding.device = emb.get("device", s.embedding.device)
    s.embedding.dimension = emb.get("dimension", s.embedding.dimension)
    s.embedding.normalize = emb.get("normalize", s.embedding.normalize)
    s.embedding.batch_size = emb.get("batch_size", s.embedding.batch_size)

    # ── Chunking ──
    ch = raw.get("chunking", {})
    s.chunking.small_size = ch.get("small_size", ch.get("size", s.chunking.small_size))
    s.chunking.small_overlap = ch.get("small_overlap", ch.get("overlap", s.chunking.small_overlap))
    s.chunking.big_size = ch.get("big_size", s.chunking.big_size)
    s.chunking.big_overlap = ch.get("big_overlap", s.chunking.big_overlap)
    s.chunking.strategy = ch.get("strategy", s.chunking.strategy)
    s.chunking.min_chunk_size = ch.get("min_chunk_size", s.chunking.min_chunk_size)

    # ── Vector DB ──
    vdb = raw.get("vector_db", {})
    s.vector_db.provider = vdb.get("provider", s.vector_db.provider)
    s.vector_db.qdrant_url = vdb.get("qdrant_url", s.vector_db.qdrant_url)
    s.vector_db.qdrant_api_key = _get_secret("QDRANT_API_KEY", vdb.get("qdrant_api_key", ""))
    s.vector_db.milvus_host = vdb.get("milvus_host", s.vector_db.milvus_host)
    s.vector_db.milvus_port = vdb.get("milvus_port", s.vector_db.milvus_port)
    s.vector_db.chroma_path = vdb.get("chroma_path", s.vector_db.chroma_path)
    s.vector_db.collection_name = vdb.get("collection_name", s.vector_db.collection_name)
    s.vector_db.distance_metric = vdb.get("distance_metric", s.vector_db.distance_metric)

    # ── PostgreSQL ──
    pg = raw.get("postgres", {})
    s.postgres.host = _get_secret("PG_HOST", pg.get("host", s.postgres.host))
    s.postgres.port = int(_get_secret("PG_PORT", str(pg.get("port", s.postgres.port))))
    s.postgres.user = _get_secret("PG_USER", pg.get("user", s.postgres.user))
    s.postgres.password = _get_secret("PG_PASSWORD", pg.get("password", ""))
    s.postgres.database = _get_secret("PG_DATABASE", pg.get("database", s.postgres.database))

    # ── MinIO ──
    mio = raw.get("minio", {})
    s.minio.endpoint = mio.get("endpoint", s.minio.endpoint)
    s.minio.access_key = _get_secret("MINIO_ACCESS_KEY", mio.get("access_key", s.minio.access_key))
    s.minio.secret_key = _get_secret("MINIO_SECRET_KEY", mio.get("secret_key", s.minio.secret_key))
    s.minio.secure = mio.get("secure", s.minio.secure)
    s.minio.raw_bucket = mio.get("raw_bucket", s.minio.raw_bucket)
    s.minio.template_bucket = mio.get("template_bucket", s.minio.template_bucket)
    s.minio.generated_bucket = mio.get("generated_bucket", s.minio.generated_bucket)

    # ── MQ ──
    mq = raw.get("mq", {})
    s.mq.provider = mq.get("provider", s.mq.provider)
    s.mq.rabbitmq_url = _get_secret("RABBITMQ_URL", mq.get("rabbitmq_url", s.mq.rabbitmq_url))
    s.mq.parse_queue = mq.get("parse_queue", s.mq.parse_queue)
    s.mq.embed_queue = mq.get("embed_queue", s.mq.embed_queue)
    s.mq.generate_queue = mq.get("generate_queue", s.mq.generate_queue)

    # ── Redis ──
    rd = raw.get("redis", {})
    s.redis.url = _get_secret("REDIS_URL", rd.get("url", s.redis.url))
    s.redis.cache_ttl = rd.get("cache_ttl", s.redis.cache_ttl)

    # ── Retrieval ──
    ret = raw.get("retrieval", {})
    s.retrieval.top_k = ret.get("top_k", s.retrieval.top_k)
    s.retrieval.final_k = ret.get("final_k", s.retrieval.final_k)
    s.retrieval.rerank_model = ret.get("rerank_model", s.retrieval.rerank_model)
    s.retrieval.semantic_weight = ret.get("semantic_weight", s.retrieval.semantic_weight)
    s.retrieval.freshness_weight = ret.get("freshness_weight", s.retrieval.freshness_weight)
    s.retrieval.keyword_weight = ret.get("keyword_weight", s.retrieval.keyword_weight)

    # ── Ingest ──
    ing = raw.get("ingest", {})
    s.ingest.max_file_size_mb = ing.get("max_file_size_mb", s.ingest.max_file_size_mb)
    s.ingest.ocr_enabled = ing.get("ocr_enabled", s.ingest.ocr_enabled)
    s.ingest.ocr_lang = ing.get("ocr_lang", s.ingest.ocr_lang)
    s.ingest.multimodal_model = ing.get("multimodal_model", s.ingest.multimodal_model)

    return s
