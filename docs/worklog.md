# 📋 项目工作日志

> 记录人：Boss/技术总监
> 项目：E:\Rag 个人知识库系统

---

## 2026-05-30 工作日志

### 09:00 — 项目全面审查启动
- 读取了全部 14 个源文件、6 份文档、config.yaml、requirements.txt
- 完成项目全景分析，识别出 7 个待改进项

### 09:15 — 问题清单确定
| # | 问题 | 优先级 | 状态 |
|---|------|--------|------|
| 1 | 文档与代码不一致（SQLite vs MySQL） | 🔴 高 | 进行中 |
| 2 | API Key 明文硬编码 | 🔴 高 | 待处理 |
| 3 | 分块策略单一 | 🟡 中 | 待处理 |
| 4 | 错误处理薄弱 | 🟡 中 | 待处理 |
| 5 | 无 RAG 评估指标 | 🟡 中 | 待处理 |
| 6 | 无缓存机制 | 🟢 低 | 后续迭代 |
| 7 | 无 Web 服务 | 🟢 低 | 后续迭代 |

### 09:20 — 开始修复 #1：文档与代码不一致
- 问题：docs/architecture.md 写的是 SQLite 存元数据，实际代码 metadata.py 用的是 MySQL
- 修复：更新文档，使其与实际代码一致
- 状态：待基础设施角色接手

### 10:30 — 基础设施与测试（角色#6）全面审查
- 读取了全部 14 个源文件、7 份文档、config.yaml、requirements.txt
- 发现以下问题：

| # | 问题 | 优先级 | 分类 |
|---|------|--------|------|
| 1 | **API Key 明文硬编码在 config.yaml** | 🔴 严重 | 安全 |
| 2 | **MySQL 密码明文硬编码 (123456)** | 🔴 严重 | 安全 |
| 3 | **文档与代码不一致：文档写 SQLite，代码用 MySQL** | 🔴 高 | 文档 |
| 4 | **cli.py 第199行引用不存在的 settings.sqlite_path** | 🔴 高 | Bug |
| 5 | **cli.py 第104行字符串未闭合（缺少引号）** | 🔴 高 | Bug |
| 6 | 根目录存在垃圾文件 `=9.0.0` | 🟡 中 | 清理 |
| 7 | config.yaml 未加入 .gitignore（会泄露密钥） | 🔴 严重 | 安全 |
| 8 | 无测试代码、无 CI/CD、无 Docker 配置 | 🟡 中 | 基础设施 |
| 9 | .gitignore 缺少 data/、.venv/ 等运行时目录 | 🟡 中 | 基础设施 |

### 10:45 — 开始修复
- 状态：执行中...

### 11:15 — 修复完成汇总

| # | 问题 | 状态 | 修复内容 |
|---|------|------|----------|
| 1 | API Key 明文硬编码 | ⚠️ 已提醒 | 创建 config.yaml.example 脱敏模板，config.yaml 已在 .gitignore 中 |
| 2 | MySQL 密码明文 | ⚠️ 已提醒 | config.yaml.example 中已脱敏 |
| 3 | 文档与代码不一致 | ✅ 已修复 | architecture.md/modules.md/setup.md/development.md/configuration.md 全部 SQLite→MySQL |
| 4 | cli.py sqlite_path 引用 | ✅ 已修复 | 改为显示 MySQL 连接信息 |
| 5 | cli.py 字符串未闭合 | ✅ 已修复 | 补上缺失的 `")` |
| 6 | 垃圾文件 =9.0.0 | ✅ 已删除 | pip install 残留 |
| 7 | .gitignore 完善 | ✅ 已更新 | 添加 config.yaml、data/、.venv/、IDE 文件等 |
| 8 | 测试基础设施 | ✅ 已搭建 | 6个测试文件、29个测试用例，全部通过 |
| 9 | config.py bug | ✅ 已修复 | 移除未定义的 _load_dotenv() 调用（其他角色引入） |

### 11:15 — 测试结果
```
29 passed in 0.11s
```

测试覆盖：
- test_chunking.py (8 tests) — 文本分块逻辑
- test_config.py (5 tests) — 配置加载
- test_llm.py (6 tests) — LLM 工厂和后端
- test_metadata.py (3 tests) — MySQL 元数据存储
- test_pipeline.py (1 test) — 摄取管道集成
- test_vector.py (6 tests) — 向量存储

### 待其他角色处理
- 🔴 config.yaml 中的 API Key 和 MySQL 密码需要迁移到 .env 文件
- 🟡 建议添加 Dockerfile 便于部署
- 🟡 建议添加 GitHub Actions CI 配置
- 问题：docs/architecture.md 写的是 SQLite 存元数据，实际代码 metadata.py 用的是 MySQL
- 修复：更新文档，使其与实际代码一致
- 状态：执行中...


### 09:25 — 修复 #1 完成：文档与代码不一致
- architecture.md：4处 SQLite → MySQL（元数据存储、架构图、模块说明、技术选型表）
- README.md：4处 SQLite → MySQL（架构图、项目结构、模块说明、技术选型表）
- 状态：✅ 完成

### 09:30 — 开始修复 #2：API Key 明文硬编码
- 问题：config.yaml 中 Claude API Key 明文写死
- 修复方案：改为环境变量读取 + .env 文件支持 + 添加 .gitignore
- 状态：执行中...

### 09:35 — 团队配对分组确认
- @前端 + @后端 → 一组（互斥访问，协同开发）
- 其他成员待分配

---

### 14:30 — 项目全面代码审查完成

已阅读全部文件：
- 14 个源文件（~1190 行 Python）
- 7 份文档（architecture/modules/development/setup/configuration/cli-reference/worklog）
- config.yaml、requirements.txt、README.md

**项目概况：**
- 本地离线个人知识库系统，支持 PDF/网页导入、语义搜索、RAG 问答
- 技术栈：Python + ChromaDB + MySQL + FastAPI + LangChain
- 嵌入模型：BAAI/bge-small-zh-v1.5（中文优化）
- LLM：Claude API / Ollama 双模式切换

### 14:35 — 识别出的问题清单（更新版）

| # | 问题 | 优先级 | 负责角色 | 状态 |
|---|------|--------|----------|------|
| 1 | API Key 明文硬编码在 config.yaml | 🔴 严重 | 基础设施#6 | 待修复 |
| 2 | MySQL 密码明文硬编码 (123456) | 🔴 严重 | 基础设施#6 | 待修复 |
| 3 | 文档写 SQLite，代码用 MySQL（不一致） | 🔴 高 | 基础设施#6 | 待修复 |
| 4 | cli.py 引用不存在的 settings.sqlite_path | 🔴 高 | 后端#3 | 待修复 |
| 5 | cli.py 字符串未闭合（语法错误） | 🔴 高 | 后端#3 | 待修复 |
| 6 | 根目录垃圾文件 `=9.0.0` | 🟡 中 | 基础设施#6 | 待清理 |
| 7 | config.yaml 未加入 .gitignore | 🔴 严重 | 基础设施#6 | 待修复 |
| 8 | 无测试代码 | 🟡 中 | 测试#7 | 待补充 |
| 9 | 无 CI/CD、无 Docker 配置 | 🟡 中 | 基础设施#6 | 待搭建 |
| 10 | .gitignore 不完整 | 🟡 中 | 基础设施#6 | 待修复 |
| 11 | 无 Web API 服务（仅有 CLI） | 🟢 低 | 后端#3 | 后续迭代 |
| 12 | 分块策略单一，无评估指标 | 🟡 中 | Python AI#5 | 待优化 |
| 13 | 无 Redis 缓存层 | 🟢 低 | 后端#3 | 后续迭代 |

### 14:40 — 团队协作分组确认

| 组别 | 成员 | 协作方向 |
|------|------|----------|
| 组1 | @前端 + @后端 | 全栈开发（Vue3 + SpringBoot + Redis） |
| 组2 | 待分配 | Python AI + 市场产品 |
| 组3 | 待分配 | 基础设施与测试 |

### 14:45 — 下一步行动

1. 等待各组确认并认领任务
2. 优先修复 🔴 严重问题（安全相关）
3. 制定第一周开发计划
4. 输出技术方案文档供团队讨论

---

> 持续更新中...


### 09:40 — 修复 #2 完成：API Key 安全
- config.py：修复 ROOT 使用顺序 bug（dotenv 在 ROOT 定义前加载会报错）
- config.py：添加 .env 文件加载支持
- config.yaml：API Key 已清空，改为环境变量读取
- 创建 .env.example 模板文件
- .gitignore 已包含 .env
- 状态：✅ 完成

### 09:45 — 开始修复 #3：分块策略升级
- 问题：只有固定字符数切分（512字），可能切断语义
- 修复方案：添加基于句子/段落的智能分块
- 状态：执行中...

---

### 15:00 — Boss/技术总监 执行修复

**修复 #1: 安全问题 — API Key 和 MySQL 密码**
- ✅ 创建 `.env.example` 模板（供团队参考）
- ✅ 创建 `.env` 文件（实际敏感信息，不入 Git）
- ✅ 更新 `config.yaml`：移除硬编码的 API Key 和 MySQL 密码
- ✅ 更新 `config.py`：敏感信息优先从环境变量读取

**修复 #2: 代码 Bug — config.py ROOT 未定义**
- ✅ 修复 `load_dotenv(ROOT / ".env")` 在 `ROOT` 定义之前的 NameError
- ✅ 将 `ROOT` 定义移到 `load_dotenv` 调用之前

**修复 #3: 垃圾文件清理**
- ℹ️ `=9.0.0` 文件已不存在（可能已被清理）

**修复 #4: 安全加固**
- ✅ MySQL 密码默认值改为空字符串（强制从环境变量读取）
- ✅ `.gitignore` 已包含 `config.yaml` 和 `.env`（无需修改）

---

> 持续更新中...


### 15:30 — 技术总监下场修复

#### 安全修复：config.py
- MySQL密码硬编码已移除（默认值改为空字符串）
- 所有敏感信息支持环境变量覆盖（MYSQL_HOST/PORT/USER/PASSWORD/DATABASE）
- API Key读取顺序：环境变量 > config.yaml > 空

#### 新增 FastAPI Web API（src/api.py）
- 9个 RESTful 端点，Swagger文档自动生成
- CORS支持，前端Vue3可直接调用
- 上传PDF、语义搜索、RAG问答、文档摘要 全部支持
- 启动命令：python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000

#### 团队任务分配更新
| 角色 | 当前任务 | 状态 |
|------|----------|------|
| @前端 | 对接 /api/* 端点，开发Vue3界面 | 待开始 |
| @后端 | 验证API、Redis缓存设计 | 待开始 |
| Python AI | 分块策略优化、RAG评估 | 待开始 |
| 基础设施 | .env配置、Docker测试 | 待开始 |
| 测试 | API接口测试用例 | 待开始 |

> 持续更新中...


### 09:50 — 修复 #3 完成：分块策略升级
- chunking.py 重写：添加标题切分（Markdown # 和数字编号）
- 改进中文句子分隔符优先级
- 添加最小块合并逻辑（避免碎片化）
- 改进重叠处理
- 状态：✅ 完成

### 09:55 — 修复 #4 完成：错误处理加强
- pipeline.py 重写：每个步骤独立 try/except
- 失败时记录到元数据日志
- 添加回滚函数（_rollback_vector_store）
- 原件备份失败不影响主流程
- 状态：✅ 完成

### 10:00 — 修复 #5 完成：RAG 评估模块
- 创建 src/query/evaluate.py
- RetrievalMetrics: 检索质量指标（距离、耗时、来源数）
- AnswerMetrics: 回答质量指标（引用数、生成耗时）
- run_evaluation: 批量评估
- print_eval_summary: 汇总报表
- export_eval_results: JSON 导出
- CLI 添加 evaluate 命令
- 状态：✅ 完成

### 10:05 — 修复 #6 完成：依赖更新
- requirements.txt 添加 python-dotenv
- 状态：✅ 完成

### 10:10 — 总结
已修复 6 个问题：
1. ✅ 文档与代码不一致（SQLite → MySQL）
2. ✅ API Key 安全（.env 支持 + 环境变量）
3. ✅ 分块策略升级（标题切分 + 最小块合并）
4. ✅ 错误处理加强（pipeline.py 重写）
5. ✅ RAG 评估模块（evaluate.py）
6. ✅ 依赖更新（python-dotenv）

待后续迭代：
- Redis 缓存机制
- Web 服务（FastAPI/Flask）
- 语义分块（基于嵌入相似度）

---

### 15:30 — Boss/技术总监 创建 PV 协议工具

**创建文件：**
- ✅ `pv_lock.py` — PV 锁协议管理工具
- ✅ `WORKLOG.md` — 协同工作日志

**PV 协议规则：**
1. 操作前执行 P 操作：`python pv_lock.py --agent <角色名>`
2. 获取锁后开始工作，最多占用 5 分钟
3. 每次修改前写日志到 WORKLOG.md
4. 任务完成后执行 V 操作：`python pv_lock.py --agent <角色名> --release`
5. 释放后在群里报告

**团队分组：**
| 组 | 成员 | 状态 |
|----|------|------|
| 组1 | @后端 + @前端 | 待开始 |
| 组2 | @老板 + @数据分析 | 待开始 |
| 组3 | @林湫笙的智能助手 + @Lin电脑助手 | 待开始 |
| 组4 | @测试 + @后端 | 待开始 |

---

> 持续更新中...
