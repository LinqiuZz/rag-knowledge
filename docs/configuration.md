# 配置指南

## 配置文件

项目根目录下的 `config.yaml` 是唯一配置文件。所有字段都有默认值，只需修改你想自定义的部分。

## LLM 配置

### Claude 兼容 API（默认）

```yaml
llm:
  default: claude
  claude:
    model: mimo-v2.5-pro
    base_url: https://token-plan-cn.xiaomimimo.com/anthropic
```

**API Key 设置**（不要写在配置文件里）:

```bash
# Windows CMD
set ANTHROPIC_AUTH_TOKEN=your_key_here

# Windows PowerShell
$env:ANTHROPIC_AUTH_TOKEN = "your_key_here"

# Linux / macOS
export ANTHROPIC_AUTH_TOKEN=your_key_here
```

系统优先读取 `ANTHROPIC_AUTH_TOKEN`，其次 `ANTHROPIC_API_KEY`。

**可选模型:**
| 模型 | 特点 |
|------|------|
| `mimo-v2.5-pro` | 小米模型，当前默认 |
| `claude-sonnet-4-6` | Anthropic 原生，需改 base_url |
| `claude-opus-4-8` | 最强能力 |

**自定义 API 地址:**
修改 `base_url` 即可切换到任何 Anthropic API 兼容端点。
当前使用小米代理: `https://token-plan-cn.xiaomimimo.com/anthropic`

---

### Ollama 本地模型

```yaml
llm:
  default: ollama
  ollama:
    model: qwen2.5:7b
    url: http://localhost:11434
```

**安装 Ollama:**
1. 访问 https://ollama.com 下载安装
2. 拉取模型：`ollama pull qwen2.5:7b`
3. 确认服务运行：`ollama list`

**推荐模型:**
| 模型 | 大小 | 适用场景 |
|------|------|---------|
| `qwen2.5:7b` | ~4.7GB | 中文最佳平衡 |
| `llama3.1:8b` | ~4.7GB | 英文更强 |
| `qwen2.5:3b` | ~2.0GB | 轻量级，速度快 |
| `qwen2.5:14b` | ~9.0GB | 更高质量，需更多内存 |

**切换后端:**
修改 `default` 字段，或在命令行用 `--llm` 参数临时切换：
```bash
python run.py ask "问题" --llm ollama
```

---

## 嵌入模型配置

```yaml
embedding:
  model_name: BAAI/bge-small-zh-v1.5
  device: cpu
  dimension: 512
```

| 参数 | 说明 | 可选值 |
|------|------|--------|
| `model_name` | HuggingFace 模型名 | 见下表 |
| `device` | 推理设备 | `cpu` (通用) / `cuda` (有 NVIDIA GPU) |
| `dimension` | 向量维度 | 需与模型匹配 |

**可选嵌入模型:**
| 模型 | 维度 | 大小 | 特点 |
|------|------|------|------|
| `BAAI/bge-small-zh-v1.5` | 512 | ~100MB | 中文优化，推荐 |
| `BAAI/bge-base-zh-v1.5` | 768 | ~400MB | 更高精度 |
| `sentence-transformers/all-MiniLM-L6-v2` | 384 | ~90MB | 英文为主 |

**GPU 加速:**
如果有 NVIDIA GPU：
```yaml
embedding:
  device: cuda
```
安装时需要 CUDA 版 PyTorch（`requirements.txt` 已配置 `cu124`）。
首次运行会自动从 HuggingFace 下载模型（~100MB），之后从本地缓存加载。

---

## 分块配置

```yaml
chunking:
  size: 512
  overlap: 64
```

| 参数 | 说明 | 建议值 |
|------|------|--------|
| `size` | 每块目标字符数 | 256-1024 |
| `overlap` | 块间重叠字符数 | size 的 10%-20% |

**调参建议:**
- `size` 太小：上下文碎片化，搜索精度下降
- `size` 太大：嵌入质量下降，噪音增多
- `overlap` 太小：跨块信息丢失
- `overlap` 太大：存储浪费，冗余增多
- 512/64 是通用平衡点，中文文档效果不错

---

## 存储配置

```yaml
store:
  chroma_path: data/db/chroma

mysql:
  host: localhost
  port: 3306
  user: Lin
  password: "123456"  # 建议通过 .env 设置
  database: rag_meta
```

ChromaDB 路径相对于项目根目录。MySQL 连接参数按实际环境配置。

---

## 摄取配置

```yaml
ingest:
  raw_dir: data/raw
  max_file_size_mb: 50
```

| 参数 | 说明 |
|------|------|
| `raw_dir` | PDF 原件备份目录 |
| `max_file_size_mb` | 单文件大小上限，超过则拒绝导入 |

---

## 完整配置示例

**最小配置（全部用默认值）:**
```yaml
# config.yaml 可以是空文件或不存在
```

**标准配置:**
```yaml
llm:
  default: claude
  claude:
    model: claude-sonnet-4-6
    base_url: https://token-plan-cn.xiaomimimo.com/anthropic

embedding:
  model_name: BAAI/bge-small-zh-v1.5
  device: cpu

chunking:
  size: 512
  overlap: 64
```

**完全离线配置（Ollama + 本地嵌入）:**
```yaml
llm:
  default: ollama
  ollama:
    model: qwen2.5:7b
    url: http://localhost:11434

embedding:
  model_name: BAAI/bge-small-zh-v1.5
  device: cpu
```
