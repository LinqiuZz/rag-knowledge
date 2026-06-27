# 🧠 RAG Knowledge Base System

**基于检索增强生成（Retrieval-Augmented Generation）的智能知识库问答系统**

[Python](https://www.python.org/) · [ChromaDB](https://www.trychroma.com/) · [Claude API](https://www.anthropic.com/) · [BAAI/bge-small-zh](https://huggingface.co/BAAI/bge-small-zh-v1.5)

一个支持混合检索、多查询扩展、多种分块策略的本地化 RAG 系统，帮助你构建基于私有文档的精准问答能力。

## 📖 项目简介

本项目是一个**端到端的 RAG 知识库系统**，从文档导入、智能分块、向量嵌入、混合检索到 LLM 生成回答，提供完整的知识库问答解决方案。

核心设计理念：
- **准确性优先** — 只基于知识库内容回答，杜绝幻觉
- **检索质量为王** — 混合检索 + 多查询扩展，最大化召回率
- **本地化部署** — 数据不出本地，支持 Ollama / Claude 等多种 LLM 后端
- **安全可控** — 云端密钥管理、路径遍历防护、SQL 注入防护

## ✨ 核心特性

### 🔍 三种检索策略
- **语义检索**：基于向量相似度，理解语义
- **混合检索**：语义 + 关键词加权融合，适合专业术语
- **多查询扩展**：LLM 生成多个角度的查询，提高召回率

### 📄 智能文档分块
- `recursive`：按层级分隔符递归切分
- `sentence`：句子级切分，保持语义完整
- `paragraph`：段落级切分，保留上下文

### 🔐 安全体系
- 支持环境变量 / .env / 云端密钥服务
- 路径遍历防护、SQL 注入防护、SSRF 防护
- CORS 精确控制

### ⚡ 性能优化
- GPU 加速嵌入计算（5-10x 提速）
- 客户端缓存、懒加载、流式生成

## 🛠️ 技术栈

- **LLM 后端**：Claude API / Ollama
- **向量数据库**：ChromaDB
- **嵌入模型**：BAAI/bge-small-zh-v1.5
- **关系数据库**：MySQL
- **Web 框架**：FastAPI
- **命令行**：Click

## 🚀 快速开始

### 环境要求
- Python 3.10+
- MySQL 8.0+（可选，用于元数据存储）

### 安装
```bash
# 克隆项目
git clone <repository-url>
cd Rag

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入 API Key 等敏感信息
```

### 使用
```bash
# 导入文档
python run.py add docs/*.md

# 提问（默认语义检索）
python run.py ask "什么是梯度下降？"

# 混合检索（适合专业术语查询）
python run.py ask "什么是梯度下降？" --hybrid

# 多查询扩展（适合复杂问题）
python run.py ask "RAG系统的基本原理是什么？" --multi-query

# 查看知识库文档列表
python run.py list

# 启动 API 服务
python run_api.py
```

## 📁 项目结构

```
Rag/
├── config.yaml                 # 全局配置
├── run.py                      # CLI 入口
├── run_api.py                  # API 服务入口
├── requirements.txt            # Python 依赖
├── .env.example                # 环境变量模板
│
├── src/
│   ├── cli.py                  # 命令行接口
│   ├── config.py               # 配置加载与验证
│   ├── secrets.py              # 云端密钥管理
│   ├── logger.py               # 日志配置
│   │
│   ├── query/                  # 查询与检索
│   │   ├── rag.py              # RAG 问答主流程
│   │   ├── rag_enhanced.py     # 增强 RAG（多查询、重排序）
│   │   ├── search.py           # 语义检索
│   │   ├── hybrid_search.py    # 混合检索
│   │   ├── memory.py           # 会话记忆
│   │   └── summarize.py        # 摘要生成
│   │
│   ├── ingest/                 # 文档处理
│   │   ├── pipeline.py         # 导入流水线
│   │   ├── parsers.py          # 多格式解析器
│   │   ├── chunking.py         # 基础分块
│   │   ├── chunking_enhanced.py # 增强分块
│   │   ├── pdf.py              # PDF 解析
│   │   └── webpage.py          # 网页抓取
│   │
│   ├── store/                  # 存储层
│   │   ├── vector.py           # ChromaDB 向量存储
│   │   ├── embedding.py        # 嵌入管理
│   │   └── metadata.py         # MySQL 元数据
│   │
│   ├── llm/                    # LLM 后端
│   │   ├── base.py             # 基类接口
│   │   ├── claude.py           # Claude API
│   │   └── ollama.py           # Ollama 本地模型
│   │
│   └── api/                    # Web API
│       ├── app.py              # FastAPI 应用
│       └── routes.py           # API 路由
│
├── docs/                       # 知识库文档
├── knowledge_base/             # 用户知识库
├── data/                       # 数据存储
│   ├── raw/                    # 原始文件
│   └── db/                     # 数据库文件
│
├── scripts/                    # 工具脚本
│   ├── evaluate_performance.py # 性能评估
│   └── secrets_server.py       # 密钥服务示例
│
└── web/                        # 前端界面
```

## 💡 提示词优化

系统采用了多层提示词优化策略，包括：
- 基础系统提示词，确保准确性和来源标注
- 场景化提示词模板，针对不同查询类型优化
- 查询扩展提示词，提高检索召回率
- 安全检查提示词，防止生成有害内容

## 📊 性能调优建议

- **top_k**: 返回文档数，默认5，建议范围3-10
- **chunk_size**: 块大小，默认512，建议范围256-1024
- **overlap**: 重叠大小，默认64，建议范围32-128
- **检索策略选择**：简单查询用语义，专业术语用混合，复杂问题用多查询

## 🗺️ 后续规划

### 短期
- [ ] 重排序算法优化（Cross-Encoder）
- [ ] 支持更多文档格式（DOCX、XLSX）
- [ ] 添加检索评估指标（MRR、NDCG）

### 长期
- [ ] 自适应检索策略（根据查询类型自动选择）
- [ ] 多模态检索（图片、表格）
- [ ] 知识图谱集成

## 📄 许可证

MIT License