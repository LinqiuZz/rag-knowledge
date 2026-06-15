# 📜 脚本工具

## setup.py — 开发环境搭建

```bash
# 快速搭建
python scripts/setup.py

# 包含开发依赖
python scripts/setup.py --dev
```

## backup.py — 数据备份

```bash
# 备份全部（MySQL + ChromaDB + 原始文件）
python scripts/backup.py

# 仅备份 MySQL
python scripts/backup.py --mysql

# 自定义输出目录
python scripts/backup.py --output-dir /path/to/backup
```

## restore.py — 数据恢复

```bash
# 恢复 MySQL
python scripts/restore.py backup/mysql_rag_meta_20260529.sql --type mysql

# 恢复 ChromaDB
python scripts/restore.py backup/chroma_20260529 --type chroma

# 恢复原始文件
python scripts/restore.py backup/raw_20260529 --type raw
```
