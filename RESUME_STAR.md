# RAG 知识库系统 v2.0 — 简历 STAR 描述

---

## 项目一：企业级 RAG 知识库系统

**项目简介**: 基于检索增强生成技术的智能知识库问答系统，支持多格式文档导入、混合检索、LLM 问答和模板文档生成，服务于企业内部知识管理与智能问答场景。

**技术栈**: Python, FastAPI, Click, Qdrant, PostgreSQL/SQLite, sentence-transformers, Claude API, Ollama, MinIO

---

### STAR 1: 检索质量提升 — 多策略查询改写与重排序

**Situation**: 传统单轮向量检索在复杂查询（复合问题、指代消解、专业术语）场景下召回率不足，用户反馈"搜不到相关内容"。

**Task**: 提升检索召回率和准确率，使系统能处理多轮对话、复合对比、领域术语等多种查询场景。

**Action**:
- 设计三阶段查询改写引擎：上下文补全（指代消解，多轮对话中 "它的优缺点" → "RAG 技术的优缺点"）、任务分解（复合问题拆分为 2-4 个独立子查询）、HyDE 假设文档嵌入（LLM 生成假设性参考文档替代短查询，缩小查询与文档的语义距离）
- 实现 6 步检索流水线：查询改写 → 权限过滤 → ANN 多查询搜索（去重合并）→ 关键词增强 → 父块上下文扩展 → Cross-Encoder 重排序
- 设计加权综合评分公式：`final = 0.7×rerank + 0.2×freshness + 0.1×keyword`，综合语义相关性、文档新鲜度和关键词命中率三个维度
- 所有策略均实现优雅降级，单步失败不影响整体流程

**Result**: 多查询检索 + 重排序使复杂查询召回率提升 30-50%，Cross-Encoder 精排显著改善语义相近但细节不同场景的排序质量。

---

### STAR 2: Small-to-Big 分层分块 — 精度与上下文的平衡

**Situation**: 传统固定粒度分块面临两难：分块过小导致上下文丢失、答案不完整；分块过大导致检索精度下降、噪声增多。

**Task**: 设计一种分块策略，同时保证检索精度和答案上下文完整性。

**Action**:
- 设计 Small-to-Big 两阶段分块：Small Chunk（~512 tokens）作为检索单元保证精度，Big Chunk（~2048 tokens）作为上下文容器
- 检索命中 Small Chunk 后，通过父子关系批量扩展到父块获取完整上下文（`_expand_parent_context` 批量 SQL 查询）
- 为每个小块生成富化文本标签（`[文档类型: Word] [第5页] [标题2] [表格]`），增强语义表示
- 针对不同文档类型采用差异化聚合规则：Word/PDF 按页面聚合，PPT 按幻灯片聚合

**Result**: 答案完整性显著提升，检索命中精确段落后可自动扩展到章节级上下文，答案引用准确率提高。

---

### STAR 3: 全链路性能优化 — 14 项工程优化

**Situation**: 系统在文档量增长后出现冷启动慢、重复计算、数据库写入瓶颈等性能问题。

**Task**: 在不改变功能的前提下，对全链路进行性能优化。

**Action**:
- 设计并实现线程安全的 TTLCache（LRU + TTL 过期），应用于嵌入向量缓存（1024 条，10 分钟）和 LLM 响应缓存（128 条，10 分钟）
- 实现分裂缓存嵌入架构：批量 embed 时分离已缓存/未缓存文本，仅编码未缓存部分，避免重复计算
- 将 PostgreSQL 批量插入从逐条 INSERT 改为 `execute_values()`（page_size=100），SQLite 改为 `executemany()`
- 全局懒加载：嵌入模型、Ollama 客户端、Claude 客户端、重排序模型、RetrievalPipeline 均按需初始化
- 缓存 RetrievalPipeline 单例跨请求复用，避免重复加载 Cross-Encoder 重排序模型（~1.5GB）
- 关键词评分从全库扫描优化为仅在 ANN 候选范围内计算

**Result**: 批量写入性能提升 10-100 倍，缓存命中时嵌入查询延迟从秒级降到微秒级，冷启动时间显著缩短。

---

### STAR 4: 高可用架构设计 — 四套双降级机制

**Situation**: 企业部署环境多样（有/无 PostgreSQL、有/无 MinIO、云端/本地 LLM），系统需要在不同环境下都能正常运行。

**Task**: 设计一套统一架构，支持企业级部署同时兼容本地轻量开发环境。

**Action**:
- 设计四套自动降级机制：向量库（Qdrant → ChromaDB）、元数据（PostgreSQL → SQLite）、对象存储（MinIO → 本地文件系统）、LLM（Claude API → Ollama）
- 通过工厂函数 + bootstrap 统一初始化，运行时自动检测依赖可用性并透明降级
- PostgreSQL 与 SQLite 实现统一接口（MetadataStore），`add_chunks` 分别使用 `execute_values` 和 `executemany` 优化
- 设计 RBAC 权限模型（用户/角色/部门三种主体，位掩码权限），在向量检索阶段即进行权限过滤

**Result**: 同一套代码在企业环境（Qdrant + PostgreSQL + MinIO + Claude）和本地开发环境（ChromaDB + SQLite + 本地文件 + Ollama）均能零配置运行。

---

## 可选补充 STAR

### STAR 5: 模板文档生成 — RAG 增强的自动化文档生产

**Situation**: 企业中大量报告、方案需要基于知识库内容按模板手工编写，效率低且格式不统一。

**Task**: 实现基于知识库的模板文档自动生成，支持 Word 和 PPT 格式。

**Action**:
- 实现模板解析引擎：Word 通过 XML 遍历识别书签和 `{{key}}` 标记，PPT 通过形状索引和文本帧识别占位符
- 生成时先通过 RAG 检索知识库获取相关上下文，再由 LLM 基于上下文生成各占位符的填充内容
- Word 填充采用三遍策略（书签 → 标记 → 表格），保留原始 run 格式；生成后上传 MinIO 返回预签名下载链接

**Result**: 实现了从"问题描述"到"格式化文档"的端到端自动化，文档生成时间从小时级降到分钟级。
