"""网页内容提取"""

from __future__ import annotations

import re
from urllib.parse import urlparse
import ipaddress


def _validate_url(url: str) -> None:
    """验证URL安全性，防止SSRF攻击"""
    parsed = urlparse(url)

    # 只允许http和https协议
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"不支持的URL协议: {parsed.scheme}，只允许 http/https")

    # 检查是否为内网IP
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL缺少主机名")

    # 检查内网IP地址段
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise ValueError(f"禁止访问内网地址: {hostname}")
    except ValueError:
        # hostname不是IP地址，检查是否为localhost等
        if hostname in ('localhost', '127.0.0.1', '0.0.0.0', '::1'):
            raise ValueError(f"禁止访问本地地址: {hostname}")


def extract_webpage(url: str) -> dict:
    """
    抓取网页正文内容。

    Returns:
        {
            "title": str,
            "text": str,
            "url": str,
            "char_count": int,
        }
    """
    # 验证URL安全性
    _validate_url(url)

    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        raise ValueError(f"无法下载网页: {url}")

    text = trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=True,
        favor_precision=True,
    )
    if not text:
        raise ValueError(f"无法提取正文: {url}")

    text = text.strip()
    # 尝试提取标题
    metadata = trafilatura.extract(
        downloaded, output_format="json", include_comments=False
    )
    title = url
    if metadata:
        import json
        try:
            meta = json.loads(metadata)
            title = meta.get("title", url)
        except (json.JSONDecodeError, TypeError):
            pass

    return {
        "title": title,
        "text": text,
        "url": url,
        "char_count": len(text),
    }
