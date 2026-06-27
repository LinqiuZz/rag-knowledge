# RAG 知识库系统 v2.0 — 技术介绍文档

## 系统概览

企业级检索增强生成（RAG）知识库系统，支持多格式文档导入、智能检索、LLM 问答、模板文档生成和 RBAC 权限控制。采用分层架构设计，所有外部依赖均有自动降级机制。

```
技术栈
├── 框架: FastAPI (API) + Click (CLI)
├── 向量库: Qdrant (生产) / ChromaDB (开发) / Milvus (可选)
├── 嵌入模型: BGE-M3 (1024维) / BGE-small-zh (512维)
├── 重排序: Cross-Encoder (BAAI/bge-reranker-large)
├── LLM: Claude API (云端) / Ollama (本地)
├── 元数据: PostgreSQL (企业) / SQLite (本地自动降级)
├── 对象存储: MinIO (企业) / 本地文件系统 (自动降级)
└── 缓存: 自研 TTLCache (线程安全 LRU + TTL 过期)
```

---

## 一、文档摄取子系统

### 1.1 多格式深度解析

**模块**: `src/ingest/parsers.py`

支持格式: PDF（含 OCR 扫描件）、Word (.docx)、PPT (.pptx)、Excel (.xlsx)、Markdown、HTML、纯文本、代码文件

**解析能力**:
- 保留文档结构: 页码、幻灯片编号、标题层级、段落/表格/图片/文本框/页眉页脚
- 每个元素携带: 边界框、样式名、标题级别、位置坐标
- PPT 特有: 幻灯片布局名、标题、演讲者备注、文本框位置
- PDF 特有: 数字 PDF 直接解析，扫描件通过 PaddleOCR 识别

**效果**: 解析结果为结构化 JSON，下游分块器可精确按页面/幻灯片/元素类型切分，不丢失上下文信息。

### 1.2 Small-to-Big 分层分块

**模块**: `src/ingest/chunking.py`

核心策略 — 两阶段分块:

| 层级 | 大小 | 用途 |
|------|------|------|
| Small Chunk | ~512 tokens | 检索单元（高精度匹配） |
| Big Chunk | ~2048 tokens | 上下文容器（检索后扩展） |

**分块流程**:
1. 遍历解析结果，按句子边界切分超长文本（支持中英文标点）
2. 为每个小块生成富化文本标签: `[文档类型: Word] [第5页] [标题2] [表格]`
3. 同页/相邻页小块聚合为大块（PPT 按幻灯片号聚合）
4. 建立双向父子链接关系

**效果**: 检索时命中高精度小块，生成答案时扩展到父块获取完整上下文，兼顾精度与完整性。

### 1.3 统一摄取管道

**模块**: `src/ingest/pipeline.py`

完整 8 步流程:
```
文件上传 → 深度解析 → 对象存储 → 创建文档记录 → 分块 → 批量嵌入 → 向量入库 → 元数据入库 → 审计日志
```

每步均有 try/except 降级: MinIO 不可用时降级到本地文件系统，Small-to-Big 失败时降级到句子分块。

---

## 二、检索子系统

### 2.1 企业级检索流水线

**模块**: `src/query/retrieval.py`

6 步完整检索流程:

```
查询改写 → 权限过滤 → ANN 多查询搜索 → 关键词增强 → 父块上下文扩展 → Cross-Encoder 重排序 → 加权评分
```

**加权评分公式**:
```
final_score = 0.7 × rerank_score + 0.2 × freshness_score + 0.1 × keyword_score
```

| 权重 | 因子 | 说明 |
|------|------|------|
| 0.7 | rerank_score | Cross-Encoder 重排序分数 (min-max 归一化) |
| 0.2 | freshness_score | 时间衰减: `1 - days_since_update / 365` |
| 0.1 | keyword_score | 查询关键词命中率 |

**效果**: 综合语义相关性、文档新鲜度和关键词匹配三个维度排序，召回率和准确率均优于纯向量检索。

### 2.2 查询改写

**模块**: `src/query/rewriting.py`

三种策略，按序执行，每步失败自动降级到原始查询:

| 策略 | 原理 | 效果 |
|------|------|------|
| **上下文补全** (Context Compress) | 指代消解 + 查询压缩 | 多轮对话中 "它的优缺点" → "RAG 技术的优缺点" |
| **任务分解** (Task Decompose) | 复合问题拆分为 2-4 个子查询 + 回退问题 | "对比 RAG 和微调" → 4 个独立检索查询 |
| **HyDE** | LLM 生成假设性参考文档作为查询 | 假设文档比短查询更接近知识库文档的语义空间 |

**效果**: 多查询检索 + 去重合并，检索召回率提升 30-50%（对比单查询基线）。

### 2.3 Prompt 工程 — Few-Shot 与 Chain-of-Thought

**模块**: `src/query/rag.py` + `src/query/rewriting.py` + `src/query/memory.py`

在问答和查询改写环节引入两种 Prompt 工程技术，提升答案质量和推理准确性:

**Few-Shot 示例引导**:
- 在 user prompt 中注入高质量 Q&A 示例，示范来源标注格式（`[来源N]`）、结构化回答（标题 + 列表）、信息不足时的明确声明
- 覆盖范围: 问答（`rag_answer`）、多轮对话（`multi_turn_rag`）、上下文补全（`compress_context`）、HyDE（`hyde`）

**Chain-of-Thought 分步推理**:
- 在 system prompt 末尾追加分步指令: 先提取关键信息 → 逐步分析推理 → 给出最终结论
- 查询改写环节同样应用 CoT: 任务分解前先分析问题结构（涉及哪些实体、关系、是否包含比较/并列）

**开关控制**:
- API 参数: `use_few_shot`（默认开启）、`use_cot`（默认开启）
- CLI 开关: `--few-shot/--no-few-shot`、`--cot/--no-cot`
- 两项技术可独立开关，互不影响

**效果**: Few-Shot 改善答案格式一致性和来源引用规范性；CoT 引导 LLM 分步推理，减少跳步遗漏和幻觉。

### 2.4 混合检索增强

- **语义检索**: ANN (Approximate Nearest Neighbor) 向量搜索，top_k=50 候选
- **关键词增强**: 在 ANN 结果范围内计算关键词命中率（避免全库扫描）
- **多查询合并**: 多个改写查询的结果按 chunk_id 去重，保留最高语义分数

**效果**: 精确关键词匹配与语义理解互补，处理专业术语和同义词场景更鲁棒。

### 2.5 Cross-Encoder 重排序

**模型**: `BAAI/bge-reranker-large`

- 输入: (query, chunk_text) 对，文本截断 2000 字符
- 输出: 归一化重排序分数
- 降级: 模型不可用时回退到语义分数

**效果**: Cross-Encoder 对候选集精排，比 Bi-Encoder 的向量距离更准确，尤其在语义相近但细节不同的场景。

---

## 三、存储子系统

### 3.1 向量数据库

**模块**: `src/store/vector.py`

| 后端 | 定位 | 特点 |
|------|------|------|
| Qdrant | 生产环境 | 批量上传 (100点/批)，结构化过滤，自动建集合 |
| ChromaDB | 开发环境 | 轻量本地持久化，简单 where 过滤 |
| Milvus | 可选 | 企业级分布式向量库 |

工厂函数自动降级: Qdrant 不可用 → ChromaDB。

### 3.2 嵌入模型管理器

**模块**: `src/store/embedding.py`

**核心优化 — 分裂缓存架构**:
```
embed(["文本A", "文本B", "文本C"])
  → 缓存命中: [A✓, C✓]
  → 仅编码: [B]
  → 合并还原: [A_emb, B_new_emb, C_emb]
```

| 功能 | 说明 |
|------|------|
| 缓存 | TTLCache(maxsize=1024, ttl=600)，10 分钟过期 |
| 批量编码 | SentenceTransformer.encode()，可配置 batch_size |
| 查询指令 | BGE-M3: 英文前缀; BGE-small: 中文前缀 |
| 稀疏向量 | BGE-M3 支持 dense + sparse 混合检索 |

**效果**: 重复查询和文档重导入场景避免重复编码，缓存命中时延迟从秒级降到微秒级。

### 3.3 元数据存储

**模块**: `src/store/metadata.py` (PostgreSQL) + `src/store/metadata_sqlite.py` (SQLite)

**数据模型** (11 张表):
```
departments → users → user_roles ← roles
                ↓
documents → document_versions → document_chunks
                ↓                    ↓
     document_permissions      templates
                ↓
          audit_logs / ingest_log
```

**关键能力**:
- **版本管理**: 新版本自动停用旧版本所有分块 (`is_active = FALSE`)，不删除数据
- **批量写入**: PostgreSQL 使用 `execute_values()`，SQLite 使用 `executemany()`
- **RBAC 权限**: 支持用户/角色/部门三种主体类型，位掩码权限 (1=读, 2=写, 4=删)
- **自动降级**: PostgreSQL 连接失败时自动切换到 SQLite (`data/db/metadata.db`)

### 3.4 对象存储

**模块**: `src/store/storage.py`

三个桶: `rag-raw-files`（原始文件）、`rag-templates`（模板）、`rag-generated`（生成文档）

所有操作双路径: MinIO 可用时用 MinIO，否则自动降级到本地文件系统。

---

## 四、LLM 子系统

**模块**: `src/llm/ollama.py` + `src/llm/claude.py`

| 后端 | 特点 | 优化 |
|------|------|------|
| Claude API | 云端，高质量 | 响应缓存 TTLCache(128, 600s)，连接池复用 |
| Ollama | 本地部署，隐私安全 | `is_available()` 结果缓存 30 秒，懒加载客户端 |

两个后端均实现懒加载，启动时不建立连接，首次调用时初始化。

---

## 五、文档生成子系统

**模块**: `src/generation/template.py`

**流程**:
```
上传模板 → 解析占位符 → RAG 检索知识库 → LLM 生成填充内容 → 模板填充 → 上传生成文件 → 返回下载链接
```

| 模板类型 | 解析方式 | 填充方式 |
|----------|----------|----------|
| Word (.docx) | 书签 + `{{key}}` 标记 + 表格区域 | 三遍: 书签替换 → 标记替换(保留格式) → 表格填充 |
| PPT (.pptx) | 形状占位符 + `{{key}}` 标记 | 两遍: 占位符替换 → 标记替换 |

**效果**: 基于知识库上下文自动生成结构化文档，保持模板原始格式和样式。

---

## 六、API 层

**模块**: `src/api/app.py` + `src/api/routes.py`

FastAPI REST API，Swagger 文档自动生成 (`/docs`)。

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/search` | POST | 语义/混合检索 |
| `/api/ask` | POST | RAG 问答 (支持查询改写开关) |
| `/api/chat` | POST | 多轮对话 RAG |
| `/api/ingest/document` | POST | 多格式文档导入 |
| `/api/documents` | GET | 文档列表 |
| `/api/documents/{id}` | DELETE | 软删除文档 |
| `/api/templates/upload` | POST | 模板上传 (自动解析占位符) |
| `/api/generate` | POST | RAG 增强文档生成 |
| `/api/permissions` | POST | 设置文档权限 |
| `/api/summarize` | POST | 文档摘要 |
| `/api/evaluate` | POST | RAG 质量评估 |
| `/api/info` | GET | 系统信息 |
| `/api/health` | GET | 健康检查 |

---

## 七、CLI 层

**模块**: `src/cli.py`

Click + Rich 命令行工具，与 API 共享 `AppContext`。

| 命令 | 功能 |
|------|------|
| `add <files>` | 导入文件 (支持 glob) |
| `add-url <urls>` | 导入网页 |
| `search <query>` | 语义/混合搜索 |
| `ask <question>` | RAG 问答 |
| `summarize <source>` | 文档摘要 |
| `list` | 列出文档 |
| `remove <id>` | 删除文档 |
| `info` | 系统状态 |
| `check` | 健康检查 (验证所有依赖) |
| `evaluate <queries>` | RAG 评估 (支持 JSON 导出) |

---

## 八、数据流总览

### 文档导入流
```
文件 → 深度解析(保留结构) → 存储 → 分块(Small-to-Big) → 批量嵌入 → 向量入库 + 元数据入库
```

### 问答生成流
```
问题 → 查询改写(压缩/分解/HyDE) → 权限过滤 → 多查询ANN搜索 → 关键词增强 → 父块扩展 → 重排序 → 加权评分 → 构建上下文 → LLM生成答案(带来源引用)
```

---

## 九、性能优化清单

| 优化项 | 模块 | 效果 |
|--------|------|------|
| TTL 缓存 (嵌入向量) | embedding.py | 重复查询延迟: 秒级 → 微秒级 |
| 分裂缓存架构 | embedding.py | 仅编码未缓存文本，避免重复计算 |
| TTL 缓存 (LLM 响应) | claude.py | 相同问题不重复调用 API |
| 懒加载 | 全局 | 启动时间最小化，按需初始化组件 |
| 批量插入 | metadata.py | `execute_values()` 比逐条 INSERT 快 10-100x |
| 批量插入 | metadata_sqlite.py | `executemany()` 比逐条 INSERT 快 10-100x |
| 批量上传 | vector.py | Qdrant 100 点/批，减少网络往返 |
| Ollama 可用性缓存 | ollama.py | 30 秒内不重复检查，避免网络开销 |
| Pipeline 单例 | bootstrap.py | 跨请求复用 RetrievalPipeline，不重复加载重排序模型 |
| 关键词评分局部化 | retrieval.py | 仅在 ANN 结果内评分，不加载全库 |
| ANN 预过滤 | retrieval.py | top_k=50 → 重排序 → final_k=5，避免全库扫描 |
| 搜索缓存失效 | vector.py | 写入时自动清空搜索缓存，保证一致性 |
| 历史截断 | rewriting.py | 最多 6 轮，每轮 300 字符，控制 LLM 输入长度 |
| HyDE 文本截断 | rewriting.py | 假设文档限 600 字符，防止嵌入质量退化 |

---

## 十、架构设计决策

| 决策 | 设计 | 理由 |
|------|------|------|
| 双向量库 | Qdrant + ChromaDB | 生产用 Qdrant，开发用轻量 ChromaDB，工厂自动降级 |
| 双元数据 | PostgreSQL + SQLite | 企业部署用 PG，本地开发自动降级到 SQLite |
| 双存储 | MinIO + 本地文件系统 | 企业用 MinIO，无 MinIO 时透明降级 |
| 双 LLM | Claude + Ollama | 云端高质量 vs 本地隐私，按需切换 |
| 分层分块 | Small-to-Big | 小块精准检索 + 大块上下文扩展，精度与完整性兼得 |
| 服务层 | Document/Retrieval/Generation | 清晰 API 边界，解耦存储层与业务逻辑 |
| RBAC 权限 | 用户/角色/部门 | 位掩码权限，支持细粒度访问控制 |
| 版本管理 | is_active 标记 | 新版本停用旧分块，不删除历史数据，支持回溯 |
