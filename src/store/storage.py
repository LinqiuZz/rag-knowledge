"""MinIO 对象存储服务

管理原始文件、模板和生成文件的存储。

Buckets:
  - rag-raw-files:    原始上传文件
  - rag-templates:    Word/PPT 模板
  - rag-generated:    生成的文档
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)


class MinIOStorage:
    """MinIO 对象存储封装。

    支持上下文管理器:
        with MinIOStorage(settings) as storage:
            storage.upload_file(path, "doc.pdf")
    """

    def __init__(self, settings):
        from ..config import Settings
        self.settings: Settings = settings
        self._client = None
        self._enabled = False

        try:
            from minio import Minio
            cfg = settings.minio
            self._client = Minio(
                cfg.endpoint,
                access_key=cfg.access_key,
                secret_key=cfg.secret_key,
                secure=cfg.secure,
            )
            self._ensure_buckets()
            self._enabled = True
            logger.info("MinIO 连接成功: %s", cfg.endpoint)
        except ImportError:
            logger.warning("minio 包未安装，使用本地文件存储作为回退")
        except Exception as e:
            logger.warning("MinIO 连接失败 (%s)，使用本地文件存储作为回退", e)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    @property
    def enabled(self) -> bool:
        return self._enabled and self._client is not None

    @property
    def client(self):
        return self._client

    def _ensure_buckets(self):
        """确保所需的 bucket 都存在。"""
        cfg = self.settings.minio
        for bucket in [cfg.raw_bucket, cfg.template_bucket, cfg.generated_bucket]:
            if not self._client.bucket_exists(bucket):
                self._client.make_bucket(bucket)
                logger.info("创建 MinIO bucket: %s", bucket)

    # ── 上传 ──────────────────────────────────────────────────

    def upload_file(self, file_path: str | Path, object_name: str = None,
                    bucket: str = None) -> str:
        """上传本地文件到 MinIO，返回 object_name。

        Args:
            file_path: 本地文件路径
            object_name: MinIO 中的对象名（默认用文件名）
            bucket: Bucket 名（默认 raw_bucket）
        """
        cfg = self.settings.minio
        bucket = bucket or cfg.raw_bucket
        path = Path(file_path)
        object_name = object_name or path.name

        if not self.enabled:
            # 回退：复制到本地目录
            dest = Path(self.settings.raw_dir) / bucket / object_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            return str(dest)

        self._client.fput_object(bucket, object_name, str(path))
        logger.info("上传到 MinIO: %s/%s", bucket, object_name)
        return object_name

    def upload_bytes(self, data: bytes, object_name: str,
                     content_type: str = "application/octet-stream",
                     bucket: str = None) -> str:
        """上传字节数据到 MinIO。"""
        cfg = self.settings.minio
        bucket = bucket or cfg.raw_bucket

        if not self.enabled:
            dest = Path(self.settings.raw_dir) / bucket / object_name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return str(dest)

        self._client.put_object(
            bucket, object_name,
            BytesIO(data), len(data),
            content_type=content_type,
        )
        return object_name

    # ── 下载 ──────────────────────────────────────────────────

    def download_file(self, object_name: str, dest_path: str | Path,
                      bucket: str = None) -> Path:
        """从 MinIO 下载文件到本地。"""
        cfg = self.settings.minio
        bucket = bucket or cfg.raw_bucket
        dest = Path(dest_path)

        if not self.enabled:
            src = Path(self.settings.raw_dir) / bucket / object_name
            if src.exists():
                shutil.copy2(src, dest)
            return dest

        self._client.fget_object(bucket, object_name, str(dest))
        return dest

    def get_bytes(self, object_name: str, bucket: str = None) -> bytes:
        """从 MinIO 读取对象内容。"""
        cfg = self.settings.minio
        bucket = bucket or cfg.raw_bucket

        if not self.enabled:
            path = Path(self.settings.raw_dir) / bucket / object_name
            return path.read_bytes() if path.exists() else b""

        response = self._client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
        return data

    # ── 预签名 URL ────────────────────────────────────────────

    def presigned_get_url(self, object_name: str, bucket: str = None,
                          expires_seconds: int = 3600) -> str:
        """生成临时下载链接。"""
        cfg = self.settings.minio
        bucket = bucket or cfg.raw_bucket

        if not self.enabled:
            return f"file://{self.settings.raw_dir}/{bucket}/{object_name}"

        return self._client.presigned_get_object(
            bucket, object_name, expires=expires_seconds
        )

    # ── 删除 ──────────────────────────────────────────────────

    def delete_object(self, object_name: str, bucket: str = None):
        cfg = self.settings.minio
        bucket = bucket or cfg.raw_bucket

        if not self.enabled:
            path = Path(self.settings.raw_dir) / bucket / object_name
            if path.exists():
                path.unlink()
            return

        self._client.remove_object(bucket, object_name)

    # ── 模板专用 ──────────────────────────────────────────────

    def upload_template(self, file_path: str | Path, object_name: str = None) -> str:
        """上传模板文件。"""
        return self.upload_file(file_path, object_name,
                                bucket=self.settings.minio.template_bucket)

    def get_template_bytes(self, object_name: str) -> bytes:
        """获取模板字节。"""
        return self.get_bytes(object_name,
                              bucket=self.settings.minio.template_bucket)

    # ── 生成文件专用 ──────────────────────────────────────────

    def save_generated(self, data: bytes, object_name: str,
                       content_type: str = "application/octet-stream") -> str:
        """保存生成的文件。"""
        return self.upload_bytes(data, object_name, content_type,
                                 bucket=self.settings.minio.generated_bucket)

    def get_generated_url(self, object_name: str, expires: int = 3600) -> str:
        """获取生成文件的下载链接。"""
        return self.presigned_get_url(object_name,
                                      bucket=self.settings.minio.generated_bucket,
                                      expires_seconds=expires)
