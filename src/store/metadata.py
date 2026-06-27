"""PostgreSQL 元数据存储 — 企业级数据模型

完整的 RBAC 权限、版本管理、审计日志支持。

表结构：
  users               — 用户
  departments         — 部门
  roles               — 角色与权限
  documents           — 文档主表
  document_versions   — 版本历史
  document_chunks     — 文本块（含 is_active、version_id、permission_ids）
  document_permissions— 文档-权限关联
  templates           — 模板
  audit_logs          — 审计日志
  ingest_log          — 摄取日志
"""

from __future__ import annotations

import re
import json
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras
from psycopg2 import Error as PgError

from ..logger import get_logger

logger = get_logger("store.metadata")

# SQL 注入防护 — 标识符白名单
_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')


def _safe_ident(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"非法标识符: {name}")
    return name


class MetadataStore:
    """PostgreSQL 封装 — 企业级数据模型。

    支持上下文管理器:
        with MetadataStore(settings) as store:
            store.list_documents()
    """

    def __init__(self, settings):
        from ..config import Settings
        self.settings: Settings = settings
        self.config = {
            "host": settings.postgres.host,
            "port": settings.postgres.port,
            "user": settings.postgres.user,
            "password": settings.postgres.password,
            "dbname": settings.postgres.database,
        }
        self.conn = None
        self._initialized = False
        # 延迟连接：首次操作时才真正连接数据库

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ── 连接管理 ──────────────────────────────────────────────

    def _connect(self):
        """建立 PostgreSQL 连接，自动创建数据库。"""
        try:
            # 先连接到默认数据库创建目标库
            db_name = self.config["dbname"]
            conn_config = {k: v for k, v in self.config.items() if k != "dbname"}
            conn_config["dbname"] = "postgres"
            conn = psycopg2.connect(**conn_config)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)
            )
            if not cur.fetchone():
                cur.execute(
                    psycopg2.sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'")
                    .format(psycopg2.sql.Identifier(db_name))
                )
            cur.close()
            conn.close()

            # 连接到目标数据库
            self.conn = psycopg2.connect(**self.config)
            psycopg2.extras.register_uuid()
            logger.info("已连接到 PostgreSQL: %s:%s/%s",
                        self.config['host'], self.config['port'], db_name)
        except PgError as e:
            logger.error("PostgreSQL 连接失败: %s", e)
            raise

    def _ensure_connected(self):
        try:
            if self.conn is None or self.conn.closed:
                logger.info("PostgreSQL 连接已断开，尝试重连...")
                self._connect()
                if not self._initialized:
                    self._init_tables()
                    self._initialized = True
        except PgError as e:
            logger.error("PostgreSQL 重连失败: %s", e)
            raise

    def _init_tables(self):
        """初始化完整的企业级表结构。"""
        self._ensure_connected()
        cur = self.conn.cursor()

        # ── 组织架构 ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id          SERIAL PRIMARY KEY,
                parent_id   INTEGER REFERENCES departments(id),
                name        VARCHAR(200) NOT NULL,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              SERIAL PRIMARY KEY,
                name            VARCHAR(200) NOT NULL,
                account         VARCHAR(200) UNIQUE NOT NULL,
                password_hash   VARCHAR(500) NOT NULL,
                email           VARCHAR(300),
                department_id   INTEGER REFERENCES departments(id),
                is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id          SERIAL PRIMARY KEY,
                name        VARCHAR(200) UNIQUE NOT NULL,
                permissions JSONB NOT NULL DEFAULT '{}',
                description TEXT,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_roles (
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                role_id INTEGER REFERENCES roles(id) ON DELETE CASCADE,
                PRIMARY KEY (user_id, role_id)
            )
        """)

        # ── 文档管理 ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id                  SERIAL PRIMARY KEY,
                title               VARCHAR(500) NOT NULL,
                format              VARCHAR(20) NOT NULL,
                owner_id            INTEGER REFERENCES users(id),
                category_id         INTEGER,
                status              VARCHAR(20) NOT NULL DEFAULT 'active',
                latest_version_id   INTEGER,
                storage_path        VARCHAR(1000),
                meta_json_path      VARCHAR(1000),
                char_count          INTEGER DEFAULT 0,
                page_count          INTEGER,
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_versions (
                id              SERIAL PRIMARY KEY,
                doc_id          INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                version_number  INTEGER NOT NULL,
                storage_path    VARCHAR(1000) NOT NULL,
                meta_json_path  VARCHAR(1000),
                char_count      INTEGER DEFAULT 0,
                page_count      INTEGER,
                chunk_count     INTEGER DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (doc_id, version_number)
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id        VARCHAR(50) PRIMARY KEY,
                doc_id          INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                version_id      INTEGER NOT NULL REFERENCES document_versions(id) ON DELETE CASCADE,
                vector_id       VARCHAR(100),
                text            TEXT NOT NULL,
                metadata_json   JSONB NOT NULL DEFAULT '{}',
                is_active       BOOLEAN NOT NULL DEFAULT TRUE,
                permission_ids  INTEGER[] DEFAULT '{}',
                page_number     INTEGER,
                slide_number    INTEGER,
                element_type    VARCHAR(50),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ── 权限 ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_permissions (
                id              SERIAL PRIMARY KEY,
                doc_id          INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                principal_type  VARCHAR(20) NOT NULL,  -- user | role | department
                principal_id    INTEGER NOT NULL,
                mask            INTEGER NOT NULL DEFAULT 1,  -- 1=read, 2=write, 4=delete
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE (doc_id, principal_type, principal_id)
            )
        """)

        # ── 模板 ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id                  SERIAL PRIMARY KEY,
                name                VARCHAR(500) NOT NULL,
                type                VARCHAR(10) NOT NULL,  -- docx | pptx
                storage_path        VARCHAR(1000) NOT NULL,
                placeholders_schema JSONB NOT NULL DEFAULT '{}',
                owner_id            INTEGER REFERENCES users(id),
                created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ── 审计 ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id          SERIAL PRIMARY KEY,
                user_id     INTEGER REFERENCES users(id),
                action      VARCHAR(100) NOT NULL,
                target_type VARCHAR(50),
                target_id   VARCHAR(200),
                ip_address  INET,
                user_agent  TEXT,
                detail      JSONB,
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # ── 摄取日志 ──
        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingest_log (
                id          SERIAL PRIMARY KEY,
                source      VARCHAR(1000) NOT NULL,
                status      VARCHAR(20) NOT NULL,
                message     TEXT,
                doc_id      INTEGER REFERENCES documents(id),
                created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)

        # 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_active ON document_chunks(is_active) WHERE is_active = TRUE")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON document_chunks(doc_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_version ON document_chunks(version_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_logs(user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs(created_at DESC)")

        self.conn.commit()
        cur.close()
        logger.info("PostgreSQL 表结构初始化完成")

    # ── 文档 CRUD ─────────────────────────────────────────────

    def add_document(
        self, *, title: str, format: str, owner_id: int = 1,
        storage_path: str = "", char_count: int = 0,
        page_count: int = None, meta_json_path: str = "",
    ) -> int:
        """创建文档记录，返回 doc_id。"""
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO documents (title, format, owner_id, storage_path,
                                   char_count, page_count, meta_json_path)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (title, format, owner_id, storage_path, char_count, page_count, meta_json_path))
        doc_id = cur.fetchone()[0]
        self.conn.commit()
        cur.close()
        return doc_id

    def get_document(self, doc_id: int) -> dict | None:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def list_documents(self, status: str = "active") -> list[dict]:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM documents WHERE status = %s ORDER BY updated_at DESC",
            (status,)
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def update_document_status(self, doc_id: int, status: str):
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute(
            "UPDATE documents SET status = %s, updated_at = NOW() WHERE id = %s",
            (status, doc_id)
        )
        self.conn.commit()
        cur.close()

    def delete_document(self, doc_id: int):
        """软删除文档（标记为 deleted）。"""
        self.update_document_status(doc_id, "deleted")
        self.log("system", "delete", f"文档 {doc_id} 已标记删除")

    # ── 版本管理 ──────────────────────────────────────────────

    def create_version(
        self, doc_id: int, storage_path: str, meta_json_path: str = "",
        char_count: int = 0, page_count: int = None,
    ) -> int:
        """创建新版本，自动停用该文档所有旧版本块，返回 version_id。"""
        self._ensure_connected()
        cur = self.conn.cursor()

        # 获取下一个版本号
        cur.execute(
            "SELECT COALESCE(MAX(version_number), 0) + 1 FROM document_versions WHERE doc_id = %s",
            (doc_id,)
        )
        version_number = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO document_versions (doc_id, version_number, storage_path,
                                           meta_json_path, char_count, page_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (doc_id, version_number, storage_path, meta_json_path, char_count, page_count))
        version_id = cur.fetchone()[0]

        # 更新文档最新版本引用
        cur.execute(
            "UPDATE documents SET latest_version_id = %s, updated_at = NOW() WHERE id = %s",
            (version_id, doc_id)
        )

        # 停用旧版本块
        cur.execute("""
            UPDATE document_chunks
            SET is_active = FALSE
            WHERE doc_id = %s AND version_id != %s
        """, (doc_id, version_id))

        self.conn.commit()
        cur.close()
        logger.info("创建版本 %s for doc %s (version_id=%s)", version_number, doc_id, version_id)
        return version_id

    def get_version(self, version_id: int) -> dict | None:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM document_versions WHERE id = %s", (version_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def list_versions(self, doc_id: int) -> list[dict]:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM document_versions WHERE doc_id = %s ORDER BY version_number DESC",
            (doc_id,)
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    # ── 块管理 ────────────────────────────────────────────────

    def add_chunks(self, chunks: list[dict]) -> int:
        """批量插入块记录。每个 dict 需含:
        chunk_id, doc_id, version_id, text, metadata_json,
        vector_id, page_number, slide_number, element_type, permission_ids
        """
        self._ensure_connected()
        cur = self.conn.cursor()
        psycopg2.extras.execute_values(cur, """
            INSERT INTO document_chunks
                (chunk_id, doc_id, version_id, vector_id, text, metadata_json,
                 is_active, permission_ids, page_number, slide_number, element_type)
            VALUES %s
            ON CONFLICT (chunk_id) DO UPDATE SET
                text = EXCLUDED.text,
                metadata_json = EXCLUDED.metadata_json,
                is_active = TRUE
        """, [
            (c["chunk_id"], c["doc_id"], c["version_id"],
             c.get("vector_id"), c["text"],
             json.dumps(c.get("metadata_json", {}), ensure_ascii=False),
             c.get("permission_ids", []),
             c.get("page_number"), c.get("slide_number"),
             c.get("element_type"))
            for c in chunks
        ], page_size=100)
        self.conn.commit()
        cur.close()
        return len(chunks)

    def deactivate_chunks(self, doc_id: int, version_id: int = None):
        """停用指定文档（和版本）的所有块。"""
        self._ensure_connected()
        cur = self.conn.cursor()
        if version_id:
            cur.execute(
                "UPDATE document_chunks SET is_active = FALSE WHERE doc_id = %s AND version_id = %s",
                (doc_id, version_id)
            )
        else:
            cur.execute(
                "UPDATE document_chunks SET is_active = FALSE WHERE doc_id = %s",
                (doc_id,)
            )
        count = cur.rowcount
        self.conn.commit()
        cur.close()
        return count

    def get_active_chunks(self, doc_id: int, permission_ids: list[int] = None) -> list[dict]:
        """获取文档的活跃块，可选权限过滤。"""
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if permission_ids:
            cur.execute("""
                SELECT * FROM document_chunks
                WHERE doc_id = %s AND is_active = TRUE
                  AND permission_ids && %s::int[]
                ORDER BY page_number, slide_number, chunk_id
            """, (doc_id, permission_ids))
        else:
            cur.execute("""
                SELECT * FROM document_chunks
                WHERE doc_id = %s AND is_active = TRUE
                ORDER BY page_number, slide_number, chunk_id
            """, (doc_id,))
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    # ── 权限管理 ──────────────────────────────────────────────

    def set_permission(self, doc_id: int, principal_type: str, principal_id: int, mask: int = 1):
        """设置文档级权限（user/role/department）。"""
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO document_permissions (doc_id, principal_type, principal_id, mask)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (doc_id, principal_type, principal_id) DO UPDATE SET mask = EXCLUDED.mask
        """, (doc_id, principal_type, principal_id, mask))
        self.conn.commit()
        cur.close()

    def get_permissions(self, doc_id: int) -> list[dict]:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM document_permissions WHERE doc_id = %s", (doc_id,)
        )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    def get_accessible_doc_ids(self, user_id: int) -> list[int]:
        """获取用户有权访问的文档 ID 列表。"""
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT dp.doc_id
            FROM document_permissions dp
            LEFT JOIN user_roles ur ON dp.principal_type = 'role' AND dp.principal_id = ur.role_id
            WHERE (dp.principal_type = 'user' AND dp.principal_id = %s)
               OR (dp.principal_type = 'role' AND ur.user_id = %s)
               OR (dp.principal_type = 'department'
                   AND dp.principal_id = (SELECT department_id FROM users WHERE id = %s))
        """, (user_id, user_id, user_id))
        doc_ids = [r[0] for r in cur.fetchall()]
        cur.close()
        return doc_ids

    # ── 模板管理 ──────────────────────────────────────────────

    def add_template(self, name: str, type: str, storage_path: str,
                     placeholders_schema: dict, owner_id: int = 1) -> int:
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO templates (name, type, storage_path, placeholders_schema, owner_id)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (name, type, storage_path, json.dumps(placeholders_schema, ensure_ascii=False), owner_id))
        tpl_id = cur.fetchone()[0]
        self.conn.commit()
        cur.close()
        return tpl_id

    def get_template(self, tpl_id: int) -> dict | None:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM templates WHERE id = %s", (tpl_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def list_templates(self, type: str = None) -> list[dict]:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if type:
            cur.execute(
                "SELECT * FROM templates WHERE type = %s ORDER BY created_at DESC",
                (type,)
            )
        else:
            cur.execute("SELECT * FROM templates ORDER BY created_at DESC")
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    # ── 审计日志 ──────────────────────────────────────────────

    def audit(self, user_id: int, action: str, target_type: str = "",
              target_id: str = "", ip_address: str = "",
              user_agent: str = "", detail: dict = None):
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, target_type, target_id,
                                    ip_address, user_agent, detail)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_id, action, target_type, target_id,
              ip_address, user_agent, json.dumps(detail or {}, ensure_ascii=False)))
        self.conn.commit()
        cur.close()

    def get_audit_logs(self, user_id: int = None, limit: int = 100) -> list[dict]:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if user_id:
            cur.execute(
                "SELECT * FROM audit_logs WHERE user_id = %s ORDER BY created_at DESC LIMIT %s",
                (user_id, limit)
            )
        else:
            cur.execute(
                "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    # ── 摄取日志（兼容旧接口）─────────────────────────────────

    def log(self, source: str, status: str, message: str = "", doc_id: int = None):
        self._ensure_connected()
        cur = self.conn.cursor()
        cur.execute(
            "INSERT INTO ingest_log (source, status, message, doc_id) VALUES (%s, %s, %s, %s)",
            (source, status, message, doc_id)
        )
        self.conn.commit()
        cur.close()

    def get_logs(self, source: str = None, limit: int = 50) -> list[dict]:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if source:
            cur.execute(
                "SELECT * FROM ingest_log WHERE source = %s ORDER BY created_at DESC LIMIT %s",
                (source, limit)
            )
        else:
            cur.execute(
                "SELECT * FROM ingest_log ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        rows = cur.fetchall()
        cur.close()
        return [dict(r) for r in rows]

    # ── 清理 ──────────────────────────────────────────────────

    def close(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
            self.conn = None
            logger.info("PostgreSQL 连接已关闭")


# ═══════════════════════════════════════════════════════════════
# 兼容旧 MySQL 接口（过渡期）
# ═══════════════════════════════════════════════════════════════

# 如果系统检测到没有 PostgreSQL 可用，回退到旧的 MySQL MetadataStore。
# 新的 MetadataStore 已直接替换，旧代码的 add_document(source=, doc_type=, title=, ...)
# 调用方式需要适配。以下提供兼容层：

class MetadataStoreCompat(MetadataStore):
    """兼容旧 MetadataStore 接口的适配器。

    旧的调用方式:
        store.add_document(source=path, doc_type="pdf", title=title,
                           chunk_count=5, char_count=1000)

    新的调用方式:
        doc_id = store.add_document(title=title, format="pdf",
                                     storage_path=path, char_count=1000)
        version_id = store.create_version(doc_id, storage_path=path, char_count=1000)
        store.add_chunks([...])
    """

    def add_document_compat(self, *, source: str, doc_type: str, title: str,
                             chunk_count: int, char_count: int) -> int:
        """兼容旧接口：source→storage_path, doc_type→format"""
        import os
        doc_id = self.add_document(
            title=title,
            format=doc_type,
            storage_path=source,
            char_count=char_count,
        )
        # 自动创建 v1 版本
        self.create_version(doc_id, storage_path=source, char_count=char_count)
        self.log(source, "success", f"摄取完成: {chunk_count} 块", doc_id=doc_id)
        return doc_id

    def get_document_by_source(self, source: str) -> dict | None:
        self._ensure_connected()
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT * FROM documents WHERE storage_path = %s ORDER BY updated_at DESC LIMIT 1",
            (source,)
        )
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def delete_document_by_source(self, source: str):
        doc = self.get_document_by_source(source)
        if doc:
            self.deactivate_chunks(doc["id"])
            self.update_document_status(doc["id"], "deleted")
            self.log(source, "delete", f"文档已删除", doc_id=doc["id"])
