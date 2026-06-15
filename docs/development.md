# 开发指南

## 项目结构

```
E:\Rag\
├── config.yaml              # 全局配置
├── run.py                   # CLI 入口 (python run.py <cmd>)
├── requirements.txt         # Python 依赖
├── README.md                # 项目简介
│
├── data/                    # 运行时数据（不入版本控制）
│   ├── raw/                 # 原始文件备份
│   │   └── pdf/             # PDF 副本
│   └── db/
│       ├── chroma/          # ChromaDB 向量库
│       └── MySQL 服务器        # 元数据存储
│
├── docs/                    # 项目文档
│   ├── architecture.md      # 系统架构
│   ├── modules.md           # 模块 API 参考
│   ├── cli-reference.md     # CLI 命令参考
│   ├── configuration.md     # 配置指南
│   ├── setup.md             # 安装与启动
│   └── development.md       # 开发指南 (本文件)
│
└── src/                     # 源代码 (~1190 行)
    ├── __init__.py
    ├── config.py            # 配置加载器
    ├── cli.py               # CLI 命令定义
    │
    ├── llm/                 # LLM 后端
    │   ├── __init__.py
    │   ├── base.py          # BaseLLM 抽象 + 工厂
    │   ├── claude.py        # Claude API 实现
    │   └── ollama.py        # Ollama 实现
    │
    ├── store/               # 存储层
    │   ├── __init__.py
    │   ├── embedding.py     # 本地嵌入模型
    │   ├── vector.py        # ChromaDB 封装
    │   └── metadata.py      # MySQL 封装
    │
    ├── ingest/              # 文档摄取
    │   ├── __init__.py
    │   ├── pdf.py           # PDF 解析
    │   ├── webpage.py       # 网页提取
    │   ├── chunking.py      # 文本分块
    │   └── pipeline.py      # 统一摄取管道
    │
    └── query/               # 查询引擎
        ├── __init__.py
        ├── search.py        # 语义搜索
        ├── summarize.py     # 文档摘要
        └── rag.py           # RAG 问答
```

## 代码风格

- **类型注解**: 使用 `from __future__ import annotations` 启用延迟求值
- **TYPE_CHECKING**: 导入仅用于类型检查的模块放在 `if TYPE_CHECKING:` 块中，避免循环导入和运行时开销
- **路径处理**: 统一使用 `pathlib.Path`，不使用 `os.path`
- **延迟加载**: 重量级依赖（如 `sentence_transformers`、`fitz`）在函数内部导入，不在模块顶层导入
- **GPU**: 默认使用 CUDA 加速嵌入推理，`config.yaml` 中 `device: cuda`
- **CLI**: 使用 Click 装饰器定义命令，Rich 做终端输出

## 扩展开发

### 添加新的 LLM 后端

1. 在 `src/llm/` 下创建新文件，如 `deepseek.py`:

```python
from .base import BaseLLM

class DeepSeekLLM(BaseLLM):
    def __init__(self, settings):
        self.model = settings.llm.deepseek_model
        self.api_key = settings.llm.deepseek_api_key

    def is_available(self) -> bool:
        return bool(self.api_key)

    def chat(self, system: str, user: str, max_tokens: int = 2048) -> str:
        # 实现 API 调用
        ...
```

2. 在 `src/llm/base.py` 的 `get_llm()` 中注册:

```python
def get_llm(backend: str, settings) -> BaseLLM:
    if backend == "claude":
        ...
    elif backend == "deepseek":
        from .deepseek import DeepSeekLLM
        return DeepSeekLLM(settings)
```

3. 在 `src/config.py` 中添加配置字段。

### 添加新的文档类型

1. 在 `src/ingest/` 下创建解析器，如 `docx.py`:

```python
def extract_docx(file_path) -> dict:
    # 返回 {"title": str, "text": str, "char_count": int}
    ...
```

2. 在 `src/ingest/pipeline.py` 中添加摄取函数:

```python
def ingest_docx(file_path, settings, vector_store, meta_store, embedder) -> dict:
    doc = extract_docx(file_path)
    chunks = split_text(doc["text"], settings.chunking.size, settings.chunking.overlap)
    # ... 后续流程与 ingest_pdf 相同
```

3. 在 `src/cli.py` 中添加命令。

### 修改分块策略

编辑 `src/ingest/chunking.py` 的 `split_text()` 函数。当前实现是递归字符切分，可以替换为:
- 基于句子的分块 (spaCy / nltk)
- 语义分块 (基于嵌入相似度)
- 固定 token 数分块 (tiktoken)

### 修改嵌入模型

修改 `config.yaml` 中的 `embedding.model_name`。需确保:
1. 模型在 HuggingFace 上可用
2. `dimension` 与模型输出维度匹配
3. 修改后需要重新导入所有文档（向量维度变化）

## 数据备份

关键数据:
- `data/db/chroma/` — 向量索引（核心）
- `MySQL (rag_meta)` — 元数据
- `data/raw/` — 原始文件备份

备份命令:
```bash
# Windows
xcopy data\db backup\db /s /e /i
xcopy data\raw backup\raw /s /e /i

# Linux / macOS
cp -r data/db backup/db
cp -r data/raw backup/raw
```

## 调试

### 查看 ChromaDB 内容

```python
import chromadb
client = chromadb.PersistentClient(path="data/db/chroma")
collection = client.get_collection("knowledge_base")
print(f"总块数: {collection.count()}")
results = collection.get(limit=5, include=["documents", "metadatas"])
for doc, meta in zip(results["documents"], results["metadatas"]):
    print(f"[{meta['title']}] {doc[:100]}...")
```

### 查看 MySQL 内容

```bash
# 使用 MySQL 客户端连接\nmysql -u Lin -p rag_meta -e "SELECT * FROM documents;"
# 使用 MySQL 客户端连接\nmysql -u Lin -p rag_meta -e "SELECT * FROM ingest_log ORDER BY created_at DESC LIMIT 10;"
```

### 手动测试 LLM

```python
from src.config import load_settings
from src.llm.base import get_llm

settings = load_settings()
llm = get_llm("claude", settings)
print(llm.is_available())
print(llm.chat("你是一个助手", "你好"))
```
