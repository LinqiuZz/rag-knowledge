#!/usr/bin/env python3
"""
云端密钥服务示例

这是一个简单的 HTTP API 服务，用于存储和提供密钥。
生产环境应使用数据库存储密钥，并添加更多安全措施。

启动方式：
    python scripts/secrets_server.py

环境变量：
    SECRETS_TOKEN: 认证令牌（必需）
    SECRETS_PORT: 服务端口（默认 8888）
    SECRETS_HOST: 监听地址（默认 127.0.0.1）

使用方式：
    # 设置环境变量
    export CLOUD_SECRETS_URL=http://127.0.0.1:8888
    export CLOUD_SECRETS_TOKEN=your_token

    # 获取密钥
    curl -H "Authorization: Bearer your_token" http://127.0.0.1:8888/secrets/ANTHROPIC_API_KEY
"""

from __future__ import annotations

import os
import sys
import json
import logging
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SecretsConfig:
    """服务配置"""
    TOKEN = os.environ.get("SECRETS_TOKEN", "")
    PORT = int(os.environ.get("SECRETS_PORT", "8888"))
    HOST = os.environ.get("SECRETS_HOST", "127.0.0.1")
    DATA_FILE = Path(__file__).parent.parent / "data" / "secrets.json"


class SecretsStore:
    """密钥存储"""

    def __init__(self, data_file: Path):
        self.data_file = data_file
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.secrets = self._load()

    def _load(self) -> dict:
        """从文件加载密钥"""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("加载密钥文件失败: %s", e)
        return {}

    def _save(self):
        """保存密钥到文件"""
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.secrets, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("保存密钥文件失败: %s", e)

    def get(self, key: str) -> str | None:
        """获取密钥"""
        return self.secrets.get(key)

    def set(self, key: str, value: str):
        """设置密钥"""
        self.secrets[key] = value
        self._save()

    def delete(self, key: str) -> bool:
        """删除密钥"""
        if key in self.secrets:
            del self.secrets[key]
            self._save()
            return True
        return False

    def list_keys(self) -> list[str]:
        """列出所有密钥名称（不包含值）"""
        return list(self.secrets.keys())


class SecretsHandler(BaseHTTPRequestHandler):
    """HTTP 请求处理器"""

    store = SecretsStore(SecretsConfig.DATA_FILE)

    def _check_auth(self) -> bool:
        """验证认证令牌"""
        if not SecretsConfig.TOKEN:
            return True  # 未配置令牌，跳过验证

        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return token == SecretsConfig.TOKEN

        # 支持查询参数传递 token
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        token = params.get("token", [None])[0]
        return token == SecretsConfig.TOKEN

    def _send_json(self, data: dict, status: int = 200):
        """发送 JSON 响应"""
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def do_GET(self):
        """处理 GET 请求"""
        if not self._check_auth():
            self._send_json({"error": "unauthorized"}, 401)
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # GET /secrets/{key}
        if path.startswith("/secrets/"):
            key = path[9:]  # 移除 "/secrets/" 前缀
            value = self.store.get(key)
            if value is not None:
                self._send_json({"value": value})
            else:
                self._send_json({"error": "not found"}, 404)
            return

        # GET /secrets (列出所有密钥名称)
        if path == "/secrets":
            keys = self.store.list_keys()
            self._send_json({"keys": keys})
            return

        # GET /health
        if path == "/health":
            self._send_json({"status": "ok"})
            return

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        """处理 POST 请求"""
        if not self._check_auth():
            self._send_json({"error": "unauthorized"}, 401)
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # 读取请求体
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self._send_json({"error": "invalid json"}, 400)
            return

        # POST /secrets/get
        if path == "/secrets/get":
            key = data.get("name") or data.get("key")
            if not key:
                self._send_json({"error": "missing name or key"}, 400)
                return

            value = self.store.get(key)
            if value is not None:
                self._send_json({"value": value})
            else:
                self._send_json({"error": "not found"}, 404)
            return

        # POST /secrets (设置密钥)
        if path == "/secrets":
            key = data.get("key")
            value = data.get("value")
            if not key or value is None:
                self._send_json({"error": "missing key or value"}, 400)
                return

            self.store.set(key, value)
            self._send_json({"message": "ok"})
            return

        self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        """处理 DELETE 请求"""
        if not self._check_auth():
            self._send_json({"error": "unauthorized"}, 401)
            return

        parsed = urlparse(self.path)
        path = parsed.path

        # DELETE /secrets/{key}
        if path.startswith("/secrets/"):
            key = path[9:]
            if self.store.delete(key):
                self._send_json({"message": "deleted"})
            else:
                self._send_json({"error": "not found"}, 404)
            return

        self._send_json({"error": "not found"}, 404)

    def log_message(self, format, *args):
        """自定义日志格式"""
        logger.info("%s - %s", self.client_address[0], format % args)


def main():
    """启动服务"""
    if not SecretsConfig.TOKEN:
        logger.warning("警告: 未设置 SECRETS_TOKEN 环境变量，服务将不需要认证")
        logger.warning("生产环境请务必设置认证令牌")

    server = HTTPServer((SecretsConfig.HOST, SecretsConfig.PORT), SecretsHandler)
    logger.info("密钥服务启动: http://%s:%d", SecretsConfig.HOST, SecretsConfig.PORT)
    logger.info("数据文件: %s", SecretsConfig.DATA_FILE)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务停止")
        server.shutdown()


if __name__ == "__main__":
    main()
