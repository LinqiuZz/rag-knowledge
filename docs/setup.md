# 安装与启动

## 环境要求

| 依赖 | 最低版本 | 说明 |
|------|---------|------|
| Python | 3.10+ | 推荐 3.11 或 3.12 |
| pip | 22+ | 随 Python 安装 |
| 磁盘空间 | ~1GB | 嵌入模型 ~100MB + 依赖 ~500MB |
| 内存 | 4GB+ | 嵌入模型推理需要 ~1.5GB RAM |

**可选:**
- [Ollama](https://ollama.com) — 本地 LLM 推理
- NVIDIA GPU + CUDA — 加速嵌入计算

## 安装步骤

### 1. 克隆/进入项目

```bash
cd E:\Rag
```

### 2. 创建虚拟环境（推荐）

```bash
python -m venv .venv

# Windows CMD
.venv\Scripts\activate

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

**依赖清单:**
| 包 | 用途 | 大小 |
|----|------|------|
| chromadb | 向量数据库 | ~50MB |
| pymupdf | PDF 解析 | ~30MB |
| trafilatura | 网页提取 | ~20MB |
| sentence-transformers | 本地嵌入 | ~300MB (含 PyTorch) |
| anthropic | Claude SDK | ~5MB |
| ollama | Ollama SDK | ~1MB |
| click | CLI 框架 | ~1MB |
| rich | 终端美化 | ~5MB |
| pyyaml | 配置解析 | ~1MB |

> **注意**: `sentence-transformers` 会拉取 PyTorch。如果只需要 Claude API + 不需要本地嵌入，可以跳过安装 `sentence-transformers`（但搜索功能将不可用）。

### 4. 设置 API Key

```bash
# Windows CMD
set ANTHROPIC_AUTH_TOKEN=your_key_here

# Windows PowerShell
$env:ANTHROPIC_AUTH_TOKEN = "your_key_here"

# Linux / macOS
export ANTHROPIC_AUTH_TOKEN=your_key_here
```

系统优先读取 `ANTHROPIC_AUTH_TOKEN`，其次 `ANTHROPIC_API_KEY`。

### 5. 验证安装

```bash
python run.py info
```

正常输出应显示系统状态面板。

## 首次运行

### 下载嵌入模型

首次执行任何需要嵌入的命令时（`add`、`add_url`、`search`、`ask`），系统会自动从 HuggingFace 下载 `BAAI/bge-small-zh-v1.5` 模型（~100MB）。

下载位置：
- Windows: `C:\Users\<user>\.cache\huggingface\`
- Linux/macOS: `~/.cache/huggingface/`

如果网络受限，可以手动下载后放到对应缓存目录。

### 导入第一个文档

```bash
python run.py add test.pdf
```

看到 `✓ 完成` 表示摄取成功。

### 测试搜索

```bash
python run.py search "文档中的关键词"
```

## 可选：Ollama 本地模型

### 安装 Ollama

1. 访问 https://ollama.com 下载安装包
2. 安装后启动服务：`ollama serve`
3. 拉取模型：`ollama pull qwen2.5:7b`

### 验证

```bash
ollama list          # 查看已下载的模型
ollama run qwen2.5:7b  # 交互测试
```

### 在知识库中使用

```bash
python run.py ask "问题" --llm ollama
```

或修改 `config.yaml` 将 `default` 改为 `ollama`。

## GPU 加速

项目默认启用 CUDA（`config.yaml` 中 `device: cuda`）。`requirements.txt` 已配置安装 CUDA 版 PyTorch (`cu124`)。

如果安装 PyTorch 时遇到问题，手动安装：
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu124
```

如需改用 CPU，修改 `config.yaml`：
```yaml
embedding:
  device: cpu
```

## 常见问题

### Q: 首次运行很慢？
A: 首次需要下载嵌入模型 (~100MB)，后续从本地缓存加载，秒级启动。

### Q: `pip install` 报 PyTorch 相关错误？
A: 确保 Python 版本 >= 3.10。如果磁盘空间不足，可以只安装核心依赖：
```bash
pip install chromadb pymupdf trafilatura anthropic click rich pyyaml
```
（跳过 sentence-transformers，但搜索功能不可用）

### Q: Ollama 连接失败？
A: 检查 Ollama 服务是否运行：`curl http://localhost:11434`。如果没有响应，运行 `ollama serve`。

### Q: PDF 导入后搜索不到？
A: 确认 PDF 是文本 PDF 而非扫描件。扫描件需要 OCR 预处理（当前版本不支持）。

### Q: 如何清除所有数据重新开始？
A: 删除 `data/db/` 目录：
```bash
# Windows
rmdir /s /q data\db

# Linux / macOS
rm -rf data/db
```
