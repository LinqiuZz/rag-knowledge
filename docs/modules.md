# 模块 API 参考

## src/config.py — 配置加载

### 数据类

```python
@dataclass
class LLMConfig:
    default: str = "claude"                          # 默认后端: claude | ollama
    claude_model: str = "mimo-v2.5-pro"              # 模型名
    claude_base_url: str = "https://..."             # API 地址 (Anthropic 兼容)
    claude_api_key: str = ""                         # 从 ANTHROPIC_AUTH_TOKEN 环境变量读取
    ollama_model: str = "qwen2.5:7b"                 # Ollama 模型名
    ollama_url: str = "http://localhost:11434"       # Ollama 服务地址

@dataclass
class EmbeddingConfig:
    model_name: str = "BAAI/bge-small-zh-v1.5"      # HuggingFace 模型名
    device: str = "cpu"                              # 推理设备: cpu | cuda
    dimension: int = 512                             # 向量维度

@dataclass
class ChunkingConfig:
    size: int = 512                                  # 每块目标字符数
    overlap: int = 64                                # 块间重叠字符数

@dataclass
class StoreConfig:
    chroma_path: str = "data/db/chroma"              # ChromaDB 目录 (相对于项目根)
    # MySQL 配置见 config.yaml 的 mysql 段

@dataclass
class IngestConfig:
    raw_dir: str = "data/raw"                        # 原始文件备份目录
    max_file_size_mb: int = 50                       # 单文件大小上限 (MB)
```

### 函数

```python
def load_settings(config_path: str | Path | None = None) -> Settings
```
从 `config.yaml` 加载配置。`config_path` 为 `None` 时使用项目根目录下的默认配置文件。缺失字段自动用默认值填充。

### 属性

```python
settings.chroma_dir   -> Path   # ChromaDB 绝对路径
settings.mysql        -> MySQLConfig   # MySQL 配置 (host/port/user/password/database)
settings.raw_dir      -> Path   # 原始文件目录绝对路径
```

---

## src/store/embedding.py — 本地嵌入模型

```python
class EmbeddingManager:
    def __init__(self, settings: Settings)
    def embed(self, texts: list[str]) -> list[list[float]]
    def embed_query(self, query: str) -> list[float]
```

- **延迟加载**: 首次调用 `embed()` 时才加载模型到内存
- **embed()**: 批量文本嵌入，返回归一化向量列表
- **embed_query()**: 单条查询嵌入，语义上等同于 `embed([query])[0]`
- 模型: `sentence-transformers` 加载 HuggingFace 模型，首次运行自动下载

---

## src/store/vector.py — ChromaDB 向量存储

```python
class VectorStore:
    COLLECTION_NAME = "knowledge_base"

    def __init__(self, settings: Settings)
    def add(self, ids, documents, embeddings, metadatas=None) -> None
    def search(self, query_embedding, top_k=5) -> dict
    def count(self) -> int
    def delete_by_source(self, source: str) -> int
    def list_sources(self) -> list[str]
```

| 方法 | 说明 |
|------|------|
| `add()` | upsert 模式：相同 ID 的块会被覆盖 |
| `search()` | cosine 距离检索，返回 `{documents, metadatas, distances}` |
| `count()` | 向量库中的总块数 |
| `delete_by_source()` | 按来源批量删除，返回删除数量 |
| `list_sources()` | 列出所有不重复的 source 值 |

存储路径: `data/db/chroma/`，ChromaDB 自动管理索引文件。

---

## src/store/metadata.py — MySQL 元数据

```python
class MetadataStore:
    def __init__(self, settings: Settings)
    def add_document(self, source, doc_type, title, chunk_count, char_count) -> int
    def log(self, source, status, message="") -> None
    def get_document(self, source) -> dict | None
    def list_documents(self) -> list[dict]
    def delete_document(self, source) -> None
    def close(self) -> None
```

### 表结构

**documents** — 已摄取文档

| 列 | 类型 | 说明 |
|----|------|------|
| id | INT AUTO_INCREMENT PK | 自增主键 |
| source | VARCHAR(500) UNIQUE | 文件路径或 URL |
| doc_type | VARCHAR(20) | `pdf` 或 `webpage` |
| title | VARCHAR(500) | 文档标题 |
| chunk_count | INT | 分块数量 |
| char_count | INT | 总字符数 |
| created_at | DATETIME | 时间戳 |

**ingest_log** — 摄取日志

| 列 | 类型 | 说明 |
|----|------|------|
| id | INT AUTO_INCREMENT PK | 自增主键 |
| source | VARCHAR(500) | 来源标识 |
| status | VARCHAR(20) | `success` 或 `error` |
| message | TEXT | 详情 |
| created_at | DATETIME | 时间戳 |

---

## src/llm/base.py — LLM 抽象接口

```python
class BaseLLM(ABC):
    def chat(self, system: str, user: str, max_tokens: int = 2048) -> str
    def is_available(self) -> bool

def get_llm(backend: str, settings) -> BaseLLM
```

- `get_llm("claude", settings)` → `ClaudeLLM`
- `get_llm("ollama", settings)` → `OllamaLLM`
- 扩展新后端：继承 `BaseLLM`，在 `get_llm()` 中注册

---

## src/llm/claude.py — Claude API 后端

```python
class ClaudeLLM(BaseLLM):
    def __init__(self, settings)       # 读取 model, base_url, api_key
    def is_available(self) -> bool     # api_key 非空即可用
    def chat(self, system, user, max_tokens=2048) -> str
```

- 使用 `anthropic` SDK
- API Key 来源: 环境变量 `ANTHROPIC_API_KEY`
- 支持自定义 `base_url`（代理/中转）

---

## src/llm/ollama.py — Ollama 本地后端

```python
class OllamaLLM(BaseLLM):
    def __init__(self, settings)       # 读取 model, url
    def is_available(self) -> bool     # 尝试连接 Ollama 服务
    def chat(self, system, user, max_tokens=2048) -> str
```

- 使用 `ollama` Python SDK
- 需要本地运行 Ollama 服务 (`ollama serve`)
- `is_available()` 通过 `client.list()` 检测连接

---

## src/ingest/pdf.py — PDF 解析

```python
def extract_pdf(file_path: str | Path) -> dict
```

返回:
```python
{
    "title": str,         # 文件名（去扩展名）
    "text": str,          # 全文文本（页间用 \n\n 连接）
    "page_count": int,    # 页数
    "char_count": int,    # 字符数
}
```

- 使用 PyMuPDF (`fitz`)
- 逐页提取文本，按页拼接
- 纯文本 PDF 效果最好；扫描件 PDF 提取不到文本

---

## src/ingest/webpage.py — 网页提取

```python
def extract_webpage(url: str) -> dict
```

返回:
```python
{
    "title": str,         # 网页标题
    "text": str,          # 正文内容（去噪后）
    "url": str,           # 原始 URL
    "char_count": int,    # 字符数
}
```

- 使用 `trafilatura`
- `favor_precision=True`：宁可少提取，不要把噪音混进来
- `include_tables=True`：保留表格内容
- 自动去除导航栏、广告、页脚等

---

## src/ingest/chunking.py — 文本分块

```python
def split_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]
```

分隔符优先级:
1. `\n\n` (段落)
2. `\n` (换行)
3. `。！？.!?` (句号)
4. `；;` (分号)
5. ` ` (空格)

算法:
- 从最高优先级分隔符开始切分
- 累积片段直到超过 `chunk_size`，输出当前块
- 单个片段超长时，用下一级分隔符递归切分
- 块间添加 `overlap` 字符重叠，保证上下文连续性

---

## src/ingest/pipeline.py — 摄取管道

```python
def ingest_pdf(file_path, settings, vector_store, meta_store, embedder) -> dict
def ingest_webpage(url, settings, vector_store, meta_store, embedder) -> dict
```

统一管道步骤:
1. **验证** — 文件大小检查
2. **提取** — 调用 `extract_pdf()` 或 `extract_webpage()`
3. **分块** — 调用 `split_text()`
4. **嵌入** — 调用 `embedder.embed(chunks)`
5. **存储** — 写入 ChromaDB (向量) + MySQL (元数据)
6. **备份** — PDF 原件复制到 `data/raw/pdf/`

返回: `{"title": str, "chunks": int, "chars": int}`

---

## src/query/search.py — 语义搜索

```python
@dataclass
class SearchResult:
    text: str           # 块文本
    source: str         # 来源路径/URL
    title: str          # 文档标题
    doc_type: str       # pdf | webpage
    score: float        # cosine distance (越小越相似)
    chunk_idx: int      # 块序号

def semantic_search(query, vector_store, embedder, top_k=5) -> list[SearchResult]
```

---

## src/query/summarize.py — 文档摘要

```python
def summarize_document(source, settings, vector_store, meta_store, embedder, llm, max_chunks=20) -> str
def summarize_query(query, settings, vector_store, embedder, llm, top_k=10) -> str
```

- `summarize_document()`: 对已入库的完整文档生成摘要，按 `chunk_idx` 排序拼接，超长文档取前 `max_chunks` 块
- `summarize_query()`: 基于查询搜索相关内容，综合生成摘要

---

## src/query/rag.py — RAG 问答

```python
def rag_answer(question, settings, vector_store, embedder, llm, top_k=5) -> dict
```

返回:
```python
{
    "answer": str,          # LLM 生成的回答（带 [来源N] 引用）
    "sources": [            # 引用的来源列表
        {
            "index": int,       # 来源编号
            "title": str,       # 文档标题
            "source": str,      # 路径/URL
            "doc_type": str,    # pdf | webpage
            "score": float,     # 相似度
        }
    ]
}
```

System Prompt 规则:
- 只基于提供的参考资料回答，不编造
- 资料不足时明确说明
- 标注 `[来源N]` 引用
- 中文回答
