# 云服务部署指南

## 项目压缩

项目实际大小分析：
| 内容 | 大小 | 是否需要部署 |
|------|------|-------------|
| `.venv/` | 1.2GB | ❌ 不需要（Docker 会重新安装） |
| `data/raw/pdf/` | 4.1GB | ❌ 不需要（原始文件） |
| `data/db/` | 132MB | ✅ 向量库数据 |
| 源码 + Web | ~1MB | ✅ 必须 |

**部署只需 ~133MB**，排除 .venv 和原始 PDF 后体积从 5.4GB 压缩到 133MB。

## 快速部署

### 方式一：Docker 部署

```bash
# 构建镜像
docker build -t rag-knowledge .

# 运行容器
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/.env:/app/.env:ro \
  --name rag \
  rag-knowledge

# 访问
# 前端页面: http://localhost:8000
# API 文档: http://localhost:8000/docs
```

### 方式二：Docker Compose

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 方式三：直接部署

```bash
# 1. 安装依赖（CPU 版本，体积更小）
pip install -r requirements-cloud.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key 和数据库密码

# 3. 启动服务
python run_api.py --host 0.0.0.0 --port 8000
```

## 环境变量配置

在 `.env` 文件中配置：

```env
# Claude API
ANTHROPIC_API_KEY=your_api_key

# MySQL (可选)
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=rag_meta
```

## 云服务商部署

### 阿里云 / 腾讯云

1. 创建 ECS/CVM 实例（2核4G 即可）
2. 安装 Docker
3. 上传代码并构建镜像
4. 配置安全组开放 8000 端口

### Vercel / Railway

由于需要持久化存储向量库，建议使用支持持久卷的服务：
- Railway: 支持 Volume
- Fly.io: 支持 Volume
- Render: 支持 Persistent Disk

### 本地内网穿透

如果部署在本地，可用 frp/ngrok 暴露到公网：

```bash
# ngrok
ngrok http 8000

# frp 配置
[rag]
type = http
local_port = 8000
custom_domains = rag.yourdomain.com
```

## 访问方式

部署成功后：
- **前端页面**: `http://your-server:8000/`
- **API 文档**: `http://your-server:8000/docs`
- **健康检查**: `http://your-server:8000/api/health`
