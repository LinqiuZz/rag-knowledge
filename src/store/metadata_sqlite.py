"""SQLite 元数据存储 — PostgreSQL 的轻量级替代

当 PostgreSQL 不可用时自动使用，提供相同的接口。
数据存储在本地 data/db/metadata.db 文件中。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..logger import get_logger

logger = get_logger("store.metadata_sqlite")

# 项目根目录
_ROOT = Path(__file__).resolve().parent.parent.parent


class MetadataStore:
    """SQLite 元数据存储 — 与 PostgreSQL MetadataStore 接口完全一致。"""

    def __init__(self, settings):
        from ..config import Settings
        self.settings: Settings = settings
        db_path = _ROOT / "data" / "db" / "metadata.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_tables()
        logger.info("SQLite 元数据库: %s", db_path)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    # ── 表初始化 ──────────────────────────────────────────────

    def _init_tables(self):
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                format          TEXT NOT NULL,
                owner_id        INTEGER DEFAULT 1,
                status          TEXT NOT NULL DEFAULT 'active',
                latest_version_id INTEGER,
                storage_path    TEXT,
                char_count      INTEGER DEFAULT 0,
                page_count      INTEGER,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_versions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id          INTEGER NOT NULL,
                version_number  INTEGER NOT NULL,
                storage_path    TEXT NOT NULL,
                char_count      INTEGER DEFAULT 0,
                page_count      INTEGER,
                chunk_count     INTEGER DEFAULT 0,
                created_at      TEXT NOT NULL,
                UNIQUE (doc_id, version_number),
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                chunk_id        TEXT PRIMARY KEY,
                doc_id          INTEGER NOT NULL,
                version_id      INTEGER NOT NULL,
                vector_id       TEXT,
                text            TEXT NOT NULL,
                metadata_json   TEXT DEFAULT '{}',
                is_active       INTEGER NOT NULL DEFAULT 1,
                page_number     INTEGER,
                slide_number    INTEGER,
                element_type    TEXT,
                created_at      TEXT NOT NULL,
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS document_permissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_id          INTEGER NOT NULL,
                principal_type  TEXT NOT NULL,
                principal_id    INTEGER NOT NULL,
                mask            INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL,
                UNIQUE (doc_id, principal_type, principal_id),
                FOREIGN KEY (doc_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL,
                type                TEXT NOT NULL,
                storage_path        TEXT NOT NULL,
                placeholders_schema TEXT DEFAULT '{}',
                owner_id            INTEGER DEFAULT 1,
                created_at          TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                action      TEXT NOT NULL,
                target_type TEXT,
                target_id   TEXT,
                detail      TEXT,
                created_at  TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS ingest_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                source      TEXT NOT NULL,
                status      TEXT NOT NULL,
                message     TEXT,
                doc_id      INTEGER,
                created_at  TEXT NOT NULL
            )
        """)

        # 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_active ON document_chunks(is_active)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON document_chunks(doc_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status)")

        self.conn.commit()
        cur.close()

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # ── 文档 CRUD ─────────────────────────────────────────────

    def add_document(self, *, title: str, format: str, owner_id: int = 1,
                     storage_path: str = "", char_count: int = 0,
                     page_count: int = None, **kwargs) -> int:
        now = self._now()
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO documents (title, format, owner_id, storage_path, char_count, page_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, format, owner_id, storage_path, char_count, page_count, now, now))
        doc_id = cur.lastrowid
        self.conn.commit()
        cur.close()
        return doc_id

    def get_document(self, doc_id: int) -> dict | None:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def list_documents(self, status: str = "active") -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM documents WHERE status = ? ORDER BY updated_at DESC", (status,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def update_document_status(self, doc_id: int, status: str):
        cur = self.conn.cursor()
        cur.execute("UPDATE documents SET status = ?, updated_at = ? WHERE id = ?",
                    (status, self._now(), doc_id))
        self.conn.commit()
        cur.close()

    def delete_document(self, doc_id: int):
        self.update_document_status(doc_id, "deleted")
        self.log("system", "delete", f"文档 {doc_id} 已标记删除")

    # ── 版本管理 ──────────────────────────────────────────────

    def create_version(self, doc_id: int, storage_path: str, char_count: int = 0,
                       page_count: int = None, **kwargs) -> int:
        now = self._now()
        cur = self.conn.cursor()
        cur.execute("SELECT COALESCE(MAX(version_number), 0) + 1 FROM document_versions WHERE doc_id = ?",
                    (doc_id,))
        version_number = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO document_versions (doc_id, version_number, storage_path, char_count, page_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (doc_id, version_number, storage_path, char_count, page_count, now))
        version_id = cur.lastrowid

        cur.execute("UPDATE documents SET latest_version_id = ?, updated_at = ? WHERE id = ?",
                    (version_id, now, doc_id))
        cur.execute("UPDATE document_chunks SET is_active = 0 WHERE doc_id = ? AND version_id != ?",
                    (doc_id, version_id))
        self.conn.commit()
        cur.close()
        return version_id

    def get_version(self, version_id: int) -> dict | None:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM document_versions WHERE id = ?", (version_id,))
        row = cur.fetchone()
        cur.close()
        return dict(row) if row else None

    def list_versions(self, doc_id: int) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM document_versions WHERE doc_id = ? ORDER BY version_number DESC",
                    (doc_id,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # ── 块管理 ────────────────────────────────────────────────

    def add_chunks(self, chunks: list[dict]) -> int:
        now = self._now()
        cur = self.conn.cursor()
        cur.executemany("""
            INSERT OR REPLACE INTO document_chunks
                (chunk_id, doc_id, version_id, vector_id, text, metadata_json,
                 is_active, page_number, slide_number, element_type, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
        """, [
            (c["chunk_id"], c["doc_id"], c["version_id"],
             c.get("vector_id"), c["text"],
             json.dumps(c.get("metadata_json", {}), ensure_ascii=False),
             c.get("page_number"), c.get("slide_number"),
             c.get("element_type"), now)
            for c in chunks
        ])
        self.conn.commit()
        cur.close()
        return len(chunks)

    def deactivate_chunks(self, doc_id: int, version_id: int = None) -> int:
        cur = self.conn.cursor()
        if version_id:
            cur.execute("UPDATE document_chunks SET is_active = 0 WHERE doc_id = ? AND version_id = ?",
                        (doc_id, version_id))
        else:
            cur.execute("UPDATE document_chunks SET is_active = 0 WHERE doc_id = ?", (doc_id,))
        count = cur.rowcount
        self.conn.commit()
        cur.close()
        return count

    def get_active_chunks(self, doc_id: int, permission_ids=None) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM document_chunks WHERE doc_id = ? AND is_active = 1 ORDER BY page_number, chunk_id",
                    (doc_id,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # ── 权限 ──────────────────────────────────────────────────

    def set_permission(self, doc_id: int, principal_type: str, principal_id: int, mask: int = 1):
        cur = self.conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO document_permissions (doc_id, principal_type, principal_id, mask, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (doc_id, principal_type, principal_id, mask, self._now()))
        self.conn.commit()
        cur.close()

    def get_permissions(self, doc_id: int) -> list[dict]:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM document_permissions WHERE doc_id = ?", (doc_id,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    def get_accessible_doc_ids(self, user_id: int) -> list[int]:
        cur = self.conn.cursor()
        cur.execute("""
            SELECT DISTINCT doc_id FROM document_permissions
            WHERE principal_type = 'user' AND principal_id = ?
        """, (user_id,))
        doc_ids = [r[0] for r in cur.fetchall()]
        cur.close()
        return doc_ids

    # ── 模板 ──────────────────────────────────────────────────

    def add_template(self, name: str, type: str, storage_path: str,
                     placeholders_schema: dict, owner_id: int = 1) -> int:
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO templates (name, type, storage_path, placeholders_schema, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, type, storage_path, json.dumps(placeholders_schema, ensure_ascii=False),
              owner_id, self._now()))
        tpl_id = cur.lastrowid
        self.conn.commit()
        cur.close()
        return tpl_id

    def get_template(self, tpl_id: int) -> dict | None:
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM templates WHERE id = ?", (tpl_id,))
        row = cur.fetchone()
        cur.close()
        if row:
            d = dict(row)
            if isinstance(d.get("placeholders_schema"), str):
                d["placeholders_schema"] = json.loads(d["placeholders_schema"])
            return d
        return None

    def list_templates(self, type: str = None) -> list[dict]:
        cur = self.conn.cursor()
        if type:
            cur.execute("SELECT * FROM templates WHERE type = ? ORDER BY created_at DESC", (type,))
        else:
            cur.execute("SELECT * FROM templates ORDER BY created_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # ── 审计 ──────────────────────────────────────────────────

    def audit(self, user_id: int, action: str, target_type: str = "",
              target_id: str = "", **kwargs):
        detail = kwargs.get("detail", {})
        cur = self.conn.cursor()
        cur.execute("""
            INSERT INTO audit_logs (user_id, action, target_type, target_id, detail, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, action, target_type, target_id,
              json.dumps(detail, ensure_ascii=False) if detail else "{}", self._now()))
        self.conn.commit()
        cur.close()

    def get_audit_logs(self, user_id: int = None, limit: int = 100) -> list[dict]:
        cur = self.conn.cursor()
        if user_id:
            cur.execute("SELECT * FROM audit_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
                        (user_id, limit))
        else:
            cur.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # ── 摄取日志 ──────────────────────────────────────────────

    def log(self, source: str, status: str, message: str = "", doc_id: int = None):
        cur = self.conn.cursor()
        cur.execute("INSERT INTO ingest_log (source, status, message, doc_id, created_at) VALUES (?, ?, ?, ?, ?)",
                    (source, status, message, doc_id, self._now()))
        self.conn.commit()
        cur.close()

    def get_logs(self, source: str = None, limit: int = 50) -> list[dict]:
        cur = self.conn.cursor()
        if source:
            cur.execute("SELECT * FROM ingest_log WHERE source = ? ORDER BY created_at DESC LIMIT ?",
                        (source, limit))
        else:
            cur.execute("SELECT * FROM ingest_log ORDER BY created_at DESC LIMIT ?", (limit,))
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        return rows

    # ── 兼容旧接口 ────────────────────────────────────────────

    def _ensure_connected(self):
        """SQLite 始终连接，此方法仅为兼容。"""
        pass

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
