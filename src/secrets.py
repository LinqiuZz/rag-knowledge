"""密钥管理模块 — 支持从云端或本地获取密钥

支持的密钥来源（按优先级）：
1. 环境变量（最高优先级）
2. 云端密钥服务（HTTP API）
3. 本地 .env 文件
4. 配置文件默认值

使用示例：
    from src.secrets import get_secret

    # 获取 API 密钥
    api_key = get_secret("ANTHROPIC_API_KEY")

    # 获取数据库密码
    db_password = get_secret("MYSQL_PASSWORD")
"""

from __future__ import annotations

import os
import json
import logging
from typing import Optional, Any
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 密钥管理器配置 ──────────────────────────────────────────────

class SecretsConfig:
    """密钥管理器配置"""

    # 云端密钥服务地址（可通过环境变量覆盖）
    CLOUD_SECRETS_URL = os.environ.get("CLOUD_SECRETS_URL", "")

    # 云端服务认证令牌
    CLOUD_SECRETS_TOKEN = os.environ.get("CLOUD_SECRETS_TOKEN", "")

    # 密钥缓存时间（秒）
    CACHE_TTL = int(os.environ.get("SECRETS_CACHE_TTL", "300"))  # 默认5分钟

    # 本地 .env 文件路径
    ENV_FILE = Path(__file__).parent.parent / ".env"


# ── 云端密钥获取 ──────────────────────────────────────────────

def _fetch_from_cloud(key: str) -> Optional[str]:
    """
    从云端密钥服务获取密钥

    支持的云端服务：
    1. 自定义 HTTP API（通过 CLOUD_SECRETS_URL 配置）
    2. AWS Secrets Manager（需要 AWS SDK）
    3. Azure Key Vault（需要 Azure SDK）
    4. HashiCorp Vault（需要 hvac 库）

    Args:
        key: 密钥名称

    Returns:
        密钥值，如果未找到返回 None
    """
    config = SecretsConfig()

    # 1. 尝试自定义 HTTP API
    if config.CLOUD_SECRETS_URL:
        return _fetch_from_http_api(key, config.CLOUD_SECRETS_URL, config.CLOUD_SECRETS_TOKEN)

    # 2. 尝试 AWS Secrets Manager
    aws_secret = _fetch_from_aws(key)
    if aws_secret is not None:
        return aws_secret

    # 3. 尝试 Azure Key Vault
    azure_secret = _fetch_from_azure(key)
    if azure_secret is not None:
        return azure_secret

    # 4. 尝试 HashiCorp Vault
    vault_secret = _fetch_from_vault(key)
    if vault_secret is not None:
        return vault_secret

    return None


def _fetch_from_http_api(key: str, url: str, token: str) -> Optional[str]:
    """从自定义 HTTP API 获取密钥"""
    try:
        import requests

        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        # 支持多种 API 格式
        # 格式1: GET /secrets/{key}
        response = requests.get(f"{url}/secrets/{key}", headers=headers, timeout=5)

        if response.status_code == 200:
            data = response.json()
            # 支持多种响应格式
            if isinstance(data, dict):
                return data.get("value") or data.get("secret") or data.get(key)
            return str(data)

        # 格式2: POST /secrets/get {name: key}
        response = requests.post(
            f"{url}/secrets/get",
            json={"name": key},
            headers=headers,
            timeout=5
        )

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                return data.get("value") or data.get("secret") or data.get(key)

    except ImportError:
        logger.debug("requests 库未安装，跳过 HTTP API 获取密钥")
    except Exception as e:
        logger.warning("从 HTTP API 获取密钥失败: %s", e)

    return None


def _fetch_from_aws(key: str) -> Optional[str]:
    """从 AWS Secrets Manager 获取密钥"""
    try:
        import boto3
        from botocore.exceptions import ClientError

        # 检查是否配置了 AWS
        if not os.environ.get("AWS_DEFAULT_REGION"):
            return None

        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=key)
        return response.get("SecretString")

    except ImportError:
        logger.debug("boto3 库未安装，跳过 AWS Secrets Manager")
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code != "ResourceNotFoundException":
            logger.warning("从 AWS Secrets Manager 获取密钥失败: %s", e)
    except Exception as e:
        logger.warning("从 AWS Secrets Manager 获取密钥失败: %s", e)

    return None


def _fetch_from_azure(key: str) -> Optional[str]:
    """从 Azure Key Vault 获取密钥"""
    try:
        from azure.keyvault.secrets import SecretClient
        from azure.identity import DefaultAzureCredential

        vault_url = os.environ.get("AZURE_KEY_VAULT_URL")
        if not vault_url:
            return None

        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
        secret = client.get_secret(key)
        return secret.value

    except ImportError:
        logger.debug("azure-keyvault-secrets 库未安装，跳过 Azure Key Vault")
    except Exception as e:
        logger.warning("从 Azure Key Vault 获取密钥失败: %s", e)

    return None


def _fetch_from_vault(key: str) -> Optional[str]:
    """从 HashiCorp Vault 获取密钥"""
    try:
        import hvac

        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        if not vault_addr or not vault_token:
            return None

        client = hvac.Client(url=vault_addr, token=vault_token)
        secret = client.secrets.kv.v2.read_secret_version(path=key)
        return secret["data"]["data"].get("value")

    except ImportError:
        logger.debug("hvac 库未安装，跳过 HashiCorp Vault")
    except Exception as e:
        logger.warning("从 HashiCorp Vault 获取密钥失败: %s", e)

    return None


# ── 本地密钥获取 ──────────────────────────────────────────────

def _load_env_file() -> dict[str, str]:
    """加载 .env 文件"""
    env_vars = {}
    env_file = SecretsConfig.ENV_FILE

    if not env_file.exists():
        return env_vars

    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过注释和空行
                if not line or line.startswith("#"):
                    continue
                # 解析 KEY=VALUE 格式
                if "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip()
                    # 移除引号
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    elif value.startswith("'") and value.endswith("'"):
                        value = value[1:-1]
                    env_vars[key] = value
    except Exception as e:
        logger.warning("加载 .env 文件失败: %s", e)

    return env_vars


# ── 主要接口 ──────────────────────────────────────────────────

# 密钥缓存
_secrets_cache: dict[str, tuple[str, float]] = {}


def get_secret(
    key: str,
    default: str = "",
    *,
    use_cloud: bool = True,
    use_env_file: bool = True,
) -> str:
    """
    获取密钥值

    按以下优先级查找：
    1. 环境变量
    2. 云端密钥服务（如果启用）
    3. 本地 .env 文件（如果启用）
    4. 默认值

    Args:
        key: 密钥名称
        default: 默认值
        use_cloud: 是否尝试从云端获取
        use_env_file: 是否尝试从 .env 文件获取

    Returns:
        密钥值
    """
    import time

    # 1. 检查环境变量（最高优先级）
    value = os.environ.get(key)
    if value:
        return value

    # 2. 尝试从云端获取
    if use_cloud:
        try:
            cloud_value = _fetch_from_cloud(key)
            if cloud_value:
                # 缓存云端获取的密钥
                _secrets_cache[key] = (cloud_value, time.time())
                return cloud_value
        except Exception as e:
            logger.warning("从云端获取密钥 '%s' 失败: %s", key, e)

    # 3. 尝试从 .env 文件获取
    if use_env_file:
        env_vars = _load_env_file()
        value = env_vars.get(key)
        if value:
            return value

    # 4. 返回默认值
    return default


def get_secret_required(key: str, **kwargs) -> str:
    """
    获取必需的密钥值

    如果密钥不存在，抛出 ValueError

    Args:
        key: 密钥名称
        **kwargs: 传递给 get_secret 的参数

    Returns:
        密钥值

    Raises:
        ValueError: 密钥不存在
    """
    value = get_secret(key, **kwargs)
    if not value:
        raise ValueError(
            f"必需的密钥 '{key}' 未配置。"
            f"请设置环境变量、云端密钥服务或 .env 文件。"
        )
    return value


def clear_cache():
    """清除密钥缓存"""
    global _secrets_cache
    _secrets_cache.clear()


# ── 便捷函数 ──────────────────────────────────────────────────

def get_anthropic_api_key() -> str:
    """获取 Anthropic API 密钥"""
    return get_secret("ANTHROPIC_API_KEY") or get_secret("ANTHROPIC_AUTH_TOKEN")


def get_mysql_password() -> str:
    """获取 MySQL 密码"""
    return get_secret("MYSQL_PASSWORD")


def get_claude_config() -> dict[str, str]:
    """获取 Claude API 配置"""
    return {
        "api_key": get_anthropic_api_key(),
        "base_url": get_secret("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        "model": get_secret("CLAUDE_MODEL", "claude-3-sonnet-20240229"),
    }


def get_mysql_config() -> dict[str, Any]:
    """获取 MySQL 配置"""
    return {
        "host": get_secret("MYSQL_HOST", "localhost"),
        "port": int(get_secret("MYSQL_PORT", "3306")),
        "user": get_secret("MYSQL_USER", "root"),
        "password": get_mysql_password(),
        "database": get_secret("MYSQL_DATABASE", "rag_meta"),
    }


# ── 云端密钥服务 API 格式示例 ──────────────────────────────────

"""
自定义 HTTP API 应该实现以下接口：

1. GET /secrets/{key}
   响应: {"value": "secret_value"} 或 {"secret": "secret_value"}

2. POST /secrets/get
   请求: {"name": "SECRET_KEY"}
   响应: {"value": "secret_value"}

认证方式：
- 请求头: Authorization: Bearer <token>

环境变量配置：
- CLOUD_SECRETS_URL: 云端密钥服务地址
- CLOUD_SECRETS_TOKEN: 认证令牌
- SECRETS_CACHE_TTL: 缓存时间（秒）

示例服务实现（Flask）：

    from flask import Flask, jsonify
    app = Flask(__name__)

    SECRETS = {
        "ANTHROPIC_API_KEY": "sk-xxx",
        "MYSQL_PASSWORD": "password123",
    }

    @app.route("/secrets/<key>")
    def get_secret(key):
        value = SECRETS.get(key)
        if value:
            return jsonify({"value": value})
        return jsonify({"error": "not found"}), 404
"""
