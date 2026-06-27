# 企业级多格式 RAG 智能知识库与文档生成系统技术方案

## 1. 文档概述

本方案描述如何构建一个企业级智能知识库，支持 Office 全家桶（Word、Excel、PPT）、PDF、图片等格式的存储、解析、语义检索和智能问答，并能够基于模板自动生成排版良好的 Word 和 PowerPoint 文件。核心目标是：**让用户以自然语言提出问题，系统从知识库中检索相关文档片段，结合大模型生成准确答案或完整文档，并保留原始排版与结构信息**。

---

## 2. 系统目标与核心能力

- **多格式摄入**：支持 .docx、.pptx、.xlsx、.pdf、.png/.jpg 等常见格式。
- **深度解析与排版保留**：提取文本、表格、图片的同时，完整保留页眉/页脚、标题层级、段落样式、表格结构、幻灯片布局等排版信息。
- **语义检索与问答（RAG）**：支持自然语言提问，返回基于知识库片段的精准答案，并标注引用来源。
- **版本管理与权限控制**：文档更新后自动淘汰旧版本块，保证检索始终命中最新内容。基于角色的细粒度权限过滤。
- **智能文档生成**：用户上传模板（Word/PPT），系统自动解析占位符，根据知识库内容或指令填充生成最终文件。
- **可扩展与高性能**：容器化部署，支持水平扩展，检索延迟可控。

---

## 3. 总体架构
┌──────────────────────────────────────────────────────────────────┐
│ 前端 (React / Vue3) │
│ 文档管理 · 智能问答界面 · 模板上传与生成 · 审计日志 │
└──────────────────────────────┬───────────────────────────────────┘
│ HTTPS
┌──────────────────────────────▼───────────────────────────────────┐
│ API 网关 (Nginx / Kong) │
│ 认证鉴权 · 限流 · 路由转发 · 日志 │
└───┬──────┬──────┬──────┬──────┬──────┬──────────────────────────┘
│ │ │ │ │ │
┌───▼──┐┌──▼───┐┌▼────┐┌▼────┐┌▼────┐┌▼───────────┐
│用户 ││文档 ││解析 ││嵌入 ││检索 ││LLM / 生成 │
│服务 ││服务 ││服务 ││服务 ││服务 ││服务 │
└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└─────┬─────┘
│ │ │ │ │ │
┌──▼───────▼──────▼──────▼──────▼──────▼────────▼────────────────┐
│ 数据与存储层 │
│ PostgreSQL (元数据/权限/模板信息) MinIO (原始文件/模板) │
│ Milvus / Qdrant (向量库) Elasticsearch (可选混合检索) │
│ Redis (缓存/会话) RabbitMQ (异步任务队列) │
└────────────────────────────────────────────────────────────────┘

**服务职责说明**：

- **用户服务**：管理用户、角色、权限，对接企业 LDAP/SSO。
- **文档服务**：管理文档元数据、分类、标签、版本、权限绑定。
- **解析服务**：将各类文档转为**携带完整排版信息的结构化 JSON**，并提取纯文本用于向量化。
- **嵌入服务**：调用嵌入模型，将文本块转为向量。
- **检索服务**：执行语义搜索、混合检索、权限过滤、重排序。
- **LLM / 生成服务**：托管大模型，处理问答生成、文档内容策划，以及 Word/PPT 文件合成。

---

## 4. 技术选型

| 模块 | 推荐方案 | 说明 |
|------|---------|------|
| 后端框架 | FastAPI (Python) | 异步性能好，与 Python 科学生态无缝集成 |
| 前端 | React + Ant Design / Vue3 + Element Plus | 成熟的中后台方案 |
| 对象存储 | MinIO（自建） | 兼容 S3，私有化部署，存放原始文件和模板 |
| 关系数据库 | PostgreSQL 14+ | 支持 JSONB，事务能力强 |
| 向量数据库 | Milvus / Qdrant / pgvector | Milvus 性能强，Qdrant 轻量且过滤友好 |
| 消息队列 | RabbitMQ / Redis Streams | 解耦上传、解析、生成等异步任务 |
| 文档解析与排版提取 | **Unstructured** / **LlamaParse** / python-docx / python-pptx / PyMuPDF | 自研或组合，确保排版元数据不丢失 |
| OCR | PaddleOCR（中文优先）/ Tesseract | 处理扫描件和图片 |
| 嵌入模型 | BGE-M3 / Jina Embeddings v2 / text2vec-large-chinese | 支持中英双语，BGE-M3 支持稠密+稀疏混合检索 |
| 重排序模型 | bge-reranker-large | 提升检索块的相关性 |
| 大语言模型 | 本地：Qwen2.5 / DeepSeek-V2；云端：GPT-4o / 通义千问 | 根据数据安全要求选择 |
| 文档生成 | python-docx / python-pptx | 从结构化 JSON 和模板生成 Office 文件 |
| 部署 | Docker + Docker Compose / Kubernetes | 容器化快速部署 |

---

## 5. 文档解析与排版保留（核心）

解析服务是系统基石，目标是将二进制文件转换为 **"富含语义标签的结构化 JSON"**，同时输出纯文本供向量化。以下分格式说明。

### 5.1 Word (.docx) 解析

**提取信息**：

- 正文段落及其样式（Normal, Heading 1-9, List Bullet 等）
- 表格（含合并单元格）
- 页眉、页脚（按节 Section）
- 脚注、尾注
- 图片及替代文本
- 文档属性（作者、创建时间）

**工具**：

- `python-docx` 可遍历段落、表格、节。
- `Unstructured` / `LlamaParse` 可输出区分元素类型的 JSON（元素类型如 `Title`, `NarrativeText`, `Header`, `Footer`, `Table`）。

**输出中间格式示例**：

```json
{
  "doc_id": "report_2025",
  "pages": [
    {
      "page_number": 5,
      "header": "内部数据 - 机密",
      "footer": "第5页 / 共20页",
      "elements": [
        { "type": "Heading2", "text": "财务概况", "style": "Heading 2" },
        { "type": "Table", "rows": [[...], [...]] },
        { "type": "Paragraph", "text": "..." }
      ]
    }
  ]
}
## 5.2 PPT (.pptx) 解析
提取信息：

每张幻灯片的标题、正文、文本框内容

布局名称（如"两栏内容"、"标题幻灯片"）

元素位置（left, top, width, height）以推断视觉关系

演讲者备注

表格、图表（图表可提取数据表，或用多模态模型生成描述）

分组、图层顺序

工具：

python-pptx 逐个读取 shapes，识别占位符索引（标题 idx=0，正文 idx=1 等）。

Unstructured 支持 pptx，输出 element 类型并包含 metadata。

输出中间格式示例：

json
{
  "slide_number": 3,
  "layout": "两栏内容",
  "title": "产品优势",
  "elements": [
    { "type": "TextBox", "position": "left", "text": "高性能\n低成本" },
    { "type": "Picture", "position": "right", "description": "由多模态模型生成的图描述：柱状图对比A/B/C指标" }
  ],
  "notes": "此处强调与竞品对比"
}
5.3 PDF 解析
数字原生 PDF：使用 PyMuPDF (fitz) 或 pdfplumber 直接提取文本、坐标、表格。

扫描件 PDF / 图片型：使用 PaddleOCR 识别文字，再结合布局模型恢复段落顺序。

表格提取推荐 Camelot 或 Unstructured 的表格检测模型。

5.4 图片与复杂图表
普通图片（照片、截图）：使用 PaddleOCR 提取其中文字。

流程图、信息图、无文字但有意义的图表：引入多模态大模型（GPT-4o / Qwen-VL）生成一段描述文本，作为该图片的替代文本参与索引。此步骤异步、非实时，仅在上传时执行一次。

5.5 最终产物
每个文件在解析后生成一个完整的文档结构 JSON，包含：

文档级元数据（文件名、类型、所有者、权限组）

页级元数据（页码、页眉、页脚）

元素列表（每个元素有类型、文本内容、样式、层级、位置、所属幻灯片等）

该 JSON 存储于 PostgreSQL JSONB 字段或 MinIO，供后续分块、检索和文档生成使用。

6. 分块策略（Small-to-Big）
采用 small-to-big 分层策略，在索引效率和上下文保留之间取得平衡。

子块（small chunk）：以元素或自然段落为粒度，如一个标题、一个段落、一个表格、一个幻灯片。

父块（big chunk）：聚合同一章节、同一幻灯片或相邻若干子块，形成更丰富的上下文。

文本表示：为每个子块生成富含元数据的文本，例如：

text
[文档类型: Word] [节: 财务分析] [页眉: 内部资料] [标题2] 营收增长情况
正文内容：本季度营收同比增长 15%，达到 1200 万元...
PPT 则以幻灯片为父块，其子块包含标题、各占位符文本、备注和图片描述。

向量化时，子块文本送入嵌入模型得到向量，并存储以下元数据到向量库 payload：

chunk_id

doc_id

version_id

page_number / slide_number

element_type（标题/正文/表格/图片描述）

permission_ids

is_active（版本控制关键字段）

纯文本内容（用于展示和关键词匹配）

7. 向量化与存储
嵌入模型选择 BGE-M3（1024 维，支持稠密+稀疏混合检索）。

向量存入 Milvus 或 Qdrant，为每个向量 payload 配置上述元数据字段，建立标量索引加速过滤。

可选：Elasticsearch 中同步存储纯文本块，支持 BM25 关键词搜索，与向量搜索混合使用。

8. 版本控制与过滤机制
问题：文档更新后，旧版块可能仍被检索到。

方案：

每个块附带 is_active 布尔字段和 version_id。

新版本上传 → 解析生成新 version_id，插入新块（is_active=true）。

将该文档旧版本所有块的 is_active 更新为 false（或直接删除）。

检索时强制过滤条件：is_active == true。

版本历史可在元数据中保留，供用户回溯。

9. 检索与重排序
9.1 检索流程
用户提问 → API 网关鉴权。

权限解析：获取当前用户有权访问的 doc_id 列表。

问题向量化，在向量库执行 ANN 搜索，过滤条件：

text
is_active == true AND doc_id in [允许列表]
返回 Top-K（如 50）个子块。

根据 small-to-big 映射，扩展为父块上下文。

9.2 重排序加权算法
综合考虑语义相关性、时效性、关键词命中，公式如下：

text
final_score = w1 * rerank_score + w2 * freshness_score + w3 * keyword_bonus
rerank_score：由 bge-reranker 等模型计算的相关性分数（0~1）。

freshness_score：基于文档最后修改时间的衰减函数，max(0, 1 - days_since_update / 365)。

keyword_bonus：问题关键词在块文本中的命中率 hit_count / len(query_keywords)。

权重建议：w1=0.7, w2=0.2, w3=0.1，可调。

若版本过滤已保证不会召回旧版，freshness_score 主要用于不同文档间的时效竞争。

10. 问答生成
重排序后取 Top-N（如 3~5）个块，连同其元数据（文档名、页码、标题层级、页眉等）构建 Prompt：

text
你是一个企业知识库助手。根据以下参考资料回答问题，并注明引用。

参考资料：
[1] 文档《Q3报告》第5页 [页眉: 内部数据] [标题2] 营收概况：
正文：Q3营收1200万，环比增长15%。
[2] 文档《产品介绍.pptx》第3页 [布局: 两栏内容]：
标题：产品优势；左栏：高性能、低成本；右栏图描述：柱状图对比...

问题：Q3营收情况如何？
回答：
LLM 生成答案后，前端展示引用高亮，用户可点击跳转至原文档预览。

11. 权限控制
采用 RBAC 模型，粒度到文档级。

每个文档在 document_permissions 表定义可访问的角色或用户组。

解析时，每个块的 permission_ids 字段继承文档权限。

检索时通过向量数据库标量过滤强制生效，绝不在应用层后过滤，保证安全。

12. 模板化文档生成
用户提供 Word/PPT 模板，系统自动填入内容，生成新文件。

12.1 模板设计规范
Word 模板：

推荐使用书签（Bookmark）定位复杂内容（表格、图片）。

纯文本区域可使用标记 {{key}}。

模板中预定义样式（标题、正文、页眉页脚）。

PPT 模板：

使用幻灯片母版中的占位符（Placeholder），约定索引（如 idx=0 标题，idx=1 正文，idx=2 图片）。

预置多种版式：标题页、内容页、两栏、图表页等。

12.2 模板解析
系统提供模板上传接口，解析后生成模板描述 JSON：

json
{
  "type": "docx",
  "placeholders": [
    { "id": "title", "type": "text", "location": "bookmark:bm_title" },
    { "id": "sales_table", "type": "table", "location": "bookmark:bm_table", "hint": "5行3列" }
  ]
}
12.3 内容填充工作流
用户上传模板，系统解析并存储。

用户提出需求："根据Q3销售数据填充此模板"。

可选：RAG 检索知识库，获取 Q3 相关数据块。

构造 Prompt，将模板占位符清单和参考资料发送给 LLM，要求输出与占位符匹配的 JSON。

校验 JSON 格式，调用 python-docx / python-pptx 填充模板：

书签替换、文本标记替换、表格插入。

PPT 按占位符索引填入文本、图表。

生成文件存入 MinIO，返回下载链接。

12.4 与知识库的集成
当填充内容需基于知识库时，RAG 检索提供准确数据，LLM 负责组织语言，避免杜撰数字。

13. 数据模型设计（关键表）
表名	关键字段	说明
users	id, name, department_id, account, password_hash	用户
departments	id, parent_id, name	部门
roles	id, name, permissions (JSON)	角色与权限
documents	id, title, format, owner_id, category_id, status, latest_version_id	文档主表
document_versions	id, doc_id, version_number, storage_path, meta_json_path	版本历史
document_chunks	chunk_id, doc_id, version_id, text, vector_id, metadata (JSONB)	文本块
document_permissions	doc_id, principal_type, principal_id, mask	权限分配
templates	id, name, type, storage_path, placeholders_schema (JSONB)	模板
audit_logs	id, user_id, action, target_id, ip, timestamp	审计日志
14. 部署与运维
容器化：所有服务打包为 Docker 镜像，使用 Docker Compose / Kubernetes 编排。

异步任务：解析、向量化、文档生成通过 RabbitMQ 消费，支持横向扩展。

监控：Prometheus + Grafana 监控服务状态，ELK 收集日志。

备份：PostgreSQL 和 MinIO 定期备份，Milvus 数据通过快照备份。

安全：全链路 HTTPS，MinIO 临时签名 URL，上传文件病毒扫描。

15. 实施路线图
第一阶段（MVP）：

实现 PDF/Word 基础解析与文本提取，简单分块。

搭建 FastAPI + Milvus + BGE 嵌入，实现单轮问答。

基本权限过滤。

第二阶段（格式扩展与排版保留）：

接入 PPT/Excel 解析，完整保留排版元数据。

实现 small-to-big 分块与重排序。

版本管理、审计日志。

第三阶段（文档生成与模板填充）：

模板解析与填充功能。

RAG 增强的 Word/PPT 生成。

企业级 UI，监控告警，集群优化。

16. 附录
16.1 关键代码示例（Python）
Word 解析片段（python-docx）：

python
from docx import Document

def parse_docx(file_path):
    doc = Document(file_path)
    result = {"pages": []}
    for section in doc.sections:
        page = {"header": section.header.paragraphs[0].text if section.header else ""}
        # ... 遍历段落、表格等
    return result
PPT 解析片段（python-pptx）：

python
from pptx import Presentation

def parse_pptx(file_path):
    prs = Presentation(file_path)
    slides_data = []
    for slide in prs.slides:
        s = {"title": slide.shapes.title.text if slide.shapes.title else ""}
        for shape in slide.shapes:
            if shape.has_text_frame:
                s["content"] = shape.text
        slides_data.append(s)
    return slides_data
模板填充（Word 书签）：

python
def fill_bookmark(doc, bookmark_name, content):
    for bookmark in doc.bookmarks:
        if bookmark.name == bookmark_name:
            bookmark.text = str(content)
16.2 配置参考
MinIO 单节点部署：minio server /data --console-address ":9001"

Milvus Standalone：docker-compose 官方文件，暴露 19530 端口。

RabbitMQ：管理插件启用，创建解析队列 doc-parse-queue。

本方案覆盖了从文件摄入、语义检索、问答生成到模板化文档输出的全链路，可直接指导企业级 RAG 知识库的构建与落地。

text

您可以直接复制以上内容，粘贴到文本编辑器中，保存为 `企业级RAG知识库技术方案.md` 即可。如果希望进一步调整表格格式、标题层级或代码高亮，也可以根据实际需要手动修改。
