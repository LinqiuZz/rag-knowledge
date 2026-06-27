# RAG Knowledge Base System v2.1

企业级检索增强生成（RAG）知识库系统，支持多格式文档导入、智能检索、LLM 问答和模板文档生成。

## 架构

```
src/
├── api/                 # FastAPI Web API
│   ├── app.py           # 应用入口
│   ├── routes.py        # 路由定义
│   └── schemas.py       # 数据模型
├── cli.py               # Click CLI
├── bootstrap.py         # 组件初始化（CLI/API 共享）
├── config.py            # 配置管理
├── ingest/              # 文档摄取
│   ├── parsers.py       # PDF/Word/PPT/Excel/Markdown 解析
│   ├── chunking.py      # 递归文本分块
│   └── pipeline.py      # 摄取管道（解析→分块→嵌入→存储）
├── query/               # 查询与生成
│   ├── retrieval.py     # 企业级检索流水线
│   ├── rag.py           # RAG 问答
│   ├── rewriting.py     # 查询改写（HyDE/任务分解/上下文补全）
│   └── memory.py        # 多轮对话
├── store/               # 存储层
│   ├── vector.py        # 向量库（ChromaDB / Qdrant）
│   ├── embedding.py     # 嵌入模型（BGE-M3 / BGE-small）
│   ├── metadata.py      # 元数据（PostgreSQL）
│   ├── metadata_sqlite.py # 元数据（SQLite 降级）
│   └── storage.py       # 对象存储（MinIO / 本地）
├── generation/          # 文档生成
│   └── template.py      # Word/PPT 模板填充
└── llm/                 # LLM 后端
    ├── ollama.py        # Ollama 本地推理
    └── claude.py        # Claude API
```

## 核心特性

- **多格式文档**: PDF / Word / PPT / Excel / Markdown / 网页
- **智能分块**: Small-to-Big 分层策略，子块检索+父块上下文扩展
- **企业级检索**: 查询改写 → ANN 搜索 → 关键词增强 → 重排序 → 加权评分
- **混合检索**: 语义向量 + BM25 关键词
- **权限控制**: 基于用户/角色的文档访问控制
- **模板生成**: 基于 RAG 上下文自动填充 Word/PPT 模板
- **多轮对话**: 上下文感知的连续问答
- **CLI + API**: Click 命令行 + FastAPI REST API 双入口

## 检索流水线

```
查询 → 查询改写 → 权限过滤 → ANN 多查询搜索 → 关键词增强 → 父块扩展 → Cross-Encoder 重排序 → 加权评分
                                                          ↓
                                              final = 0.7×rerank + 0.2×freshness + 0.1×keyword
```

## 快速开始

### 安装

```bash
git clone https://github.com/LinqiuZz/rag-knowledge.git
cd rag-knowledge
pip install -r requirements.txt
```

### 启动 API 服务

```bash
python run_api.py                  # 默认 0.0.0.0:8000
python run_api.py --port 8080      # 指定端口
python run_api.py --reload         # 开发热重载
```

Swagger 文档: http://localhost:8000/docs

### CLI 使用

```bash
# 导入文档
python run.py ingest docs/example.pdf

# 问答
python run.py ask "什么是 RAG？"

# 混合检索
python run.py ask "梯度下降原理" --hybrid

# 语义搜索
python run.py search "transformer 注意力机制"
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/search` | 语义/混合检索 |
| POST | `/api/ask` | RAG 问答 |
| POST | `/api/chat` | 多轮对话 |
| POST | `/api/ingest/document` | 文档导入 |
| GET | `/api/documents` | 文档列表 |
| DELETE | `/api/documents/{id}` | 删除文档 |
| POST | `/api/generate` | 模板文档生成 |
| POST | `/api/permissions` | 设置权限 |
| GET | `/api/info` | 系统信息 |
| GET | `/api/health` | 健康检查 |

## 配置

通过 `.env` 文件或环境变量配置:

```env
VECTOR_DB_PROVIDER=qdrant        # qdrant | chroma
EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5
LLM_BACKEND=claude               # claude | ollama
METADATA_DB_URL=postgresql://...  # 可选，自动降级到 SQLite
```

## 技术栈

- **框架**: FastAPI + Click
- **向量库**: Qdrant / ChromaDB
- **嵌入**: sentence-transformers (BGE-M3 / BGE-small)
- **LLM**: Claude API / Ollama
- **元数据**: PostgreSQL / SQLite
- **对象存储**: MinIO / 本地文件系统

## License

MIT
