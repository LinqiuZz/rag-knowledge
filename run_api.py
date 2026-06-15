#!/usr/bin/env python3
"""
启动 Web API 服务器

用法:
    python run_api.py                    # 默认启动 (0.0.0.0:8000)
    python run_api.py --port 8080        # 指定端口
    python run_api.py --host 127.0.0.1   # 仅本地访问
"""

import sys
import os
from pathlib import Path

# 自动切换到虚拟环境
def ensure_venv():
    if sys.prefix == sys.base_prefix:
        venv_python = Path(__file__).parent / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            os.execv(str(venv_python), [str(venv_python)] + sys.argv)

ensure_venv()

import argparse
import uvicorn


def main():
    parser = argparse.ArgumentParser(description="启动知识库 Web API")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址 (默认: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="监听端口 (默认: 8000)")
    parser.add_argument("--reload", action="store_true", help="开发模式（热重载）")
    
    args = parser.parse_args()
    
    print(f"[启动] 知识库 Web API")
    print(f"   地址: http://{args.host}:{args.port}")
    print(f"   文档: http://{args.host}:{args.port}/docs")
    print(f"   模式: {'开发' if args.reload else '生产'}")
    
    uvicorn.run(
        "src.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
