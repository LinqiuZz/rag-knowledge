#!/usr/bin/env python3
"""去除知识库中所有重复文档"""

import sys
import os
from pathlib import Path

# 设置环境变量以解决Windows控制台编码问题
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_settings
from src.store.metadata import MetadataStore
from src.store.vector import VectorStore


def is_valid_title(title: str) -> bool:
    """判断是否是有效的文档标题"""
    if not title or len(title) < 3:
        return False

    # 过滤掉不是真正标题的情况
    invalid_starts = ['<', '#', '/*', '//', '--', 'import ', 'from ', 'def ', 'class ', 'ifndef ', 'define ']
    for prefix in invalid_starts:
        if title.startswith(prefix):
            return False

    return True


def main():
    settings = load_settings()
    ms = MetadataStore(settings)
    vs = VectorStore(settings)

    docs = ms.list_documents()
    print(f"当前文档总数: {len(docs)}")
    print(f"当前向量块总数: {vs.count()}")

    # 按标题分组
    from collections import defaultdict
    title_groups = defaultdict(list)
    for doc in docs:
        title = doc['title']
        if is_valid_title(title):
            title_groups[title].append(doc)

    # 找出重复的文档
    total_deleted = 0
    total_chunks_deleted = 0

    for title, group in title_groups.items():
        if len(group) <= 1:
            continue

        # 按块数排序，保留块数最多的版本
        group.sort(key=lambda x: x['chunk_count'], reverse=True)
        keep = group[0]
        to_remove = group[1:]

        print(f"\n标题: {title[:50]}")
        print(f"  保留: {keep['source']} ({keep['chunk_count']} 块)")

        for doc in to_remove:
            print(f"  删除: {doc['source']} ({doc['chunk_count']} 块)")
            # 删除向量块
            count = vs.delete_by_source(doc['source'])
            # 删除元数据
            ms.delete_document(doc['source'])
            total_deleted += 1
            total_chunks_deleted += count

    print(f"\n{'='*50}")
    print(f"删除重复文档数: {total_deleted}")
    print(f"删除向量块数: {total_chunks_deleted}")

    # 统计剩余文档
    remaining = ms.list_documents()
    print(f"剩余文档数: {len(remaining)}")
    print(f"剩余向量块数: {vs.count()}")

    ms.close()


if __name__ == "__main__":
    main()
