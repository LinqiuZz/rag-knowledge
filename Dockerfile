# ============================================================
#  个人知识库系统 — 云服务部署 Docker 配置
# ============================================================

FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件（利用 Docker 缓存层）
COPY requirements-cloud.txt requirements.txt

# 安装 Python 依赖（使用 CPU 版本 PyTorch，体积更小）
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ src/
COPY web/ web/
COPY run_api.py run.py config.yaml.example ./
COPY README_ENHANCED.md ./

# 创建数据目录
RUN mkdir -p data/db data/raw

# 暴露端口
EXPOSE 8000

# 环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/api/health || exit 1

# 启动命令
CMD ["python", "run_api.py", "--host", "0.0.0.0", "--port", "8000"]
