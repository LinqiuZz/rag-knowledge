"""MySQL 元数据存储"""

from __future__ import annotations

import re
import mysql.connector
from mysql.connector import Error as MySQLError
from datetime import datetime, timezone
from ..logger import get_logger

logger = get_logger("store.metadata")
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import Settings


def _validate_db_name(name: str) -> bool:
    """验证数据库名称，防止SQL注入"""
    return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


class MetadataStore:
    """MySQL 封装，记录文档元数据和摄取历史。

    支持上下文管理器:
        with MetadataStore(settings) as store:
            store.list_documents()
    """

    def __init__(self, settings: Settings):
        self.config = {
            "host": settings.mysql.host,
            "port": settings.mysql.port,
            "user": settings.mysql.user,
            "password": settings.mysql.password,
            "database": settings.mysql.database,
            "charset": "utf8mb4",
            "collation": "utf8mb4_unicode_ci",
        }
        self.conn = None

        # 验证数据库名称
        if not _validate_db_name(self.config['database']):
            raise ValueError(f"数据库名称包含非法字符: {self.config['database']}")

        self._connect()
        self._init_tables()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _connect(self):
        """建立 MySQL 连接，如果数据库不存在则自动创建。"""
        try:
            # 先连接到 MySQL 服务器（不指定数据库）
            conn_config = {k: v for k, v in self.config.items() if k != "database"}
            conn = mysql.connector.connect(**conn_config)
            cursor = conn.cursor()

            # 创建数据库（如果不存在）
            db_name = self.config['database']
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.close()
            conn.close()

            # 连接到目标数据库
            self.conn = mysql.connector.connect(**self.config)
            logger.info("已连接到 MySQL: %s:%s/%s", self.config['host'], self.config['port'], self.config['database'])

        except MySQLError as e:
            logger.error("MySQL 连接失败: %s", e)
            raise

    def _ensure_connected(self):
        """确保数据库连接有效，必要时重连"""
        try:
            if self.conn is None or not self.conn.is_connected():
                logger.info("MySQL 连接已断开，尝试重连...")
                self._connect()
        except MySQLError as e:
            logger.error("MySQL 重连失败: %s", e)
            raise

    def _init_tables(self):
        """初始化表结构。"""
        self._ensure_connected()
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                source      VARCHAR(500) NOT NULL,
                doc_type    VARCHAR(20) NOT NULL,
                title       VARCHAR(500),
                chunk_count INT DEFAULT 0,
                char_count  INT DEFAULT 0,
                created_at  DATETIME NOT NULL,
                UNIQUE KEY uk_source (source)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ingest_log (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                source      VARCHAR(500) NOT NULL,
                status      VARCHAR(20) NOT NULL,
                message     TEXT,
                created_at  DATETIME NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)
        self.conn.commit()
        cursor.close()

    def add_document(
        self, source: str, doc_type: str, title: str,
        chunk_count: int, char_count: int,
    ) -> int:
        """记录一篇已摄取的文档，返回 id。"""
        self._ensure_connected()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute(
            """INSERT INTO documents
               (source, doc_type, title, chunk_count, char_count, created_at)
               VALUES (%s, %s, %s, %s, %s, %s)
               ON DUPLICATE KEY UPDATE
                   doc_type = VALUES(doc_type),
                   title = VALUES(title),
                   chunk_count = VALUES(chunk_count),
                   char_count = VALUES(char_count),
                   created_at = VALUES(created_at)""",
            (source, doc_type, title, chunk_count, char_count, now),
        )
        self.conn.commit()
        last_id = cursor.lastrowid
        cursor.close()

        # 写入操作日志
        self.log(source, "add", f"文档已记录: type={doc_type}, title={title}, chunks={chunk_count}, chars={char_count}")

        return last_id

    def log(self, source: str, status: str, message: str = ""):
        """记录摄取日志。"""
        self._ensure_connected()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO ingest_log (source, status, message, created_at) VALUES (%s, %s, %s, %s)",
            (source, status, message, now),
        )
        self.conn.commit()
        cursor.close()

    def get_document(self, source: str) -> dict | None:
        """获取指定文档的元数据。"""
        self._ensure_connected()
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM documents WHERE source = %s", (source,)
        )
        row = cursor.fetchone()
        cursor.close()
        return row

    def list_documents(self) -> list[dict]:
        """列出所有文档。"""
        self._ensure_connected()
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        )
        rows = cursor.fetchall()
        cursor.close()
        return rows

    def delete_document(self, source: str):
        """删除指定文档。"""
        self._ensure_connected()
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM documents WHERE source = %s", (source,))
        self.conn.commit()
        cursor.close()

        # 写入操作日志
        self.log(source, "delete", "文档已删除")

    def close(self):
        """关闭连接。"""
        if self.conn and self.conn.is_connected():
            self.conn.close()
            self.conn = None
            logger.info("MySQL 连接已关闭")
