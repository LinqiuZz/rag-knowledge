# CLI 命令参考

所有命令通过 `python run.py <command>` 调用。

## 全局选项

```
python run.py --config <path> <command>
```

| 选项 | 说明 |
|------|------|
| `--config` | 指定配置文件路径，默认使用项目根目录下的 `config.yaml` |

---

## 摄取命令

### `add` — 导入 PDF

```bash
python run.py add <file1.pdf> [file2.pdf ...]
```

**参数:**
- `files`: 一个或多个 PDF 文件路径（支持通配符）

**示例:**
```bash
python run.py add document.pdf
python run.py add *.pdf
python run.py add "E:\Documents\paper1.pdf" "E:\Documents\paper2.pdf"
```

**行为:**
1. 检查文件大小（默认上限 50MB）
2. 提取 PDF 全文文本
3. 递归分块（512 字/块，64 字重叠）
4. 本地嵌入模型生成向量
5. 存入 ChromaDB (向量) + MySQL (元数据)
6. 原件备份到 `data/raw/pdf/`

**输出示例:**
```
解析 PDF: paper.pdf
  分块完成: 42 块, 21504 字符
  生成嵌入向量...
  ✓ 完成: paper (42 块)
```

---

### `add_url` — 导入网页

```bash
python run.py add_url <url1> [url2 ...]
```

**参数:**
- `urls`: 一个或多个网页 URL

**示例:**
```bash
python run.py add_url https://example.com/article
python run.py add_url https://a.com/post1 https://b.com/post2
```

**行为:**
1. 下载网页内容
2. trafilatura 提取正文（去广告、导航、噪音）
3. 分块 → 嵌入 → 存储

---

## 查询命令

### `search` — 语义搜索

```bash
python run.py search <query> [-k N]
```

**参数:**
- `query`: 搜索关键词或自然语言描述
- `-k, --top-k`: 返回结果数量，默认 5

**示例:**
```bash
python run.py search "机器学习基础概念"
python run.py search "gradient descent" -k 10
```

**输出:**
每个结果以面板形式展示：
- 块文本预览（前 300 字符）
- 文档标题 + 相似度分数
- 来源路径

---

### `ask` — RAG 问答

```bash
python run.py ask <question> [-k N] [--llm backend]
```

**参数:**
- `question`: 自然语言问题
- `-k, --top-k`: 检索文档数量，默认 5
- `--llm`: 指定 LLM 后端，可选 `claude` 或 `ollama`

**示例:**
```bash
python run.py ask "什么是梯度下降？"
python run.py ask "这篇论文的主要贡献是什么？" -k 8
python run.py ask "对比两种算法的优劣" --llm ollama
```

**输出:**
1. LLM 生成的回答（带 `[来源N]` 引用标注）
2. 引用来源表格（标题、类型、相关度）

---

### `summarize` — 文档摘要

```bash
python run.py summarize <source> [--llm backend]
```

**参数:**
- `source`: 文档来源（文件路径或 URL），必须是已导入知识库的文档
- `--llm`: 指定 LLM 后端

**示例:**
```bash
python run.py summarize "E:\Docs\paper.pdf"
python run.py summarize "https://example.com/article" --llm ollama
```

**行为:**
1. 从向量库中取出该来源的所有块
2. 按块序号排序拼接
3. 调用 LLM 生成摘要

---

## 管理命令

### `list` — 列出文档

```bash
python run.py list
```

输出表格包含：标题、类型、块数、字符数、导入时间。

---

### `remove` — 删除文档

```bash
python run.py remove <source>
```

**参数:**
- `source`: 文档来源路径或 URL

**示例:**
```bash
python run.py remove "E:\Docs\old_paper.pdf"
```

**行为:**
- 需要确认（y/n）
- 删除 ChromaDB 中的所有相关向量块
- 删除 MySQL 中的元数据记录
- 注意：不删除 `data/raw/` 中的原件备份

---

### `info` — 系统状态

```bash
python run.py info
```

输出：
- 当前 LLM 后端和模型名
- 嵌入模型名和设备
- 文档总数和向量块总数
- 存储路径

---

## 使用场景速查

| 场景 | 命令 |
|------|------|
| 导入一篇论文 | `python run.py add paper.pdf` |
| 批量导入 | `python run.py add *.pdf` |
| 保存网页文章 | `python run.py add_url https://...` |
| 找相关内容 | `python run.py search "关键词"` |
| 基于知识库问答 | `python run.py ask "问题"` |
| 快速了解文档内容 | `python run.py summarize "path.pdf"` |
| 用本地模型问答 | `python run.py ask "问题" --llm ollama` |
| 查看库里有什么 | `python run.py list` |
| 清理不需要的文档 | `python run.py remove "source"` |
| 检查系统状态 | `python run.py info` |
