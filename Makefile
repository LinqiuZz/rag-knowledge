# ============================================================
#  个人知识库系统 — Makefile
# ============================================================

.PHONY: help install test lint format check clean docker-up docker-down

help:  ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## 安装依赖
	pip install -r requirements.txt

install-lock:  ## 安装锁定版本依赖
	pip install -r requirements-lock.txt

test:  ## 运行测试
	pytest -v

test-cov:  ## 运行测试（带覆盖率）
	pytest -v --cov=src --cov-report=term-missing

lint:  ## 代码检查
	ruff check src/ tests/

format:  ## 代码格式化
	ruff format src/ tests/

check:  ## 健康检查
	python run.py check

clean:  ## 清理临时文件
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache

docker-up:  ## 启动 Docker 服务
	docker compose up -d mysql

docker-down:  ## 停止 Docker 服务
	docker compose down

docker-full:  ## 启动全部服务（含 Ollama）
	docker compose --profile gpu up -d

add:  ## 导入 PDF（用法: make add FILE=test.pdf）
	python run.py add $(FILE)

search:  ## 搜索（用法: make search Q="关键词"）
	python run.py search "$(Q)"

ask:  ## RAG 问答（用法: make ask Q="问题"）
	python run.py ask "$(Q)"
